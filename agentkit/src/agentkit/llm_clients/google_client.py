import os
import asyncio
import functools
from typing import Dict, Any, Optional, List

import tenacity
import google.genai as genai
from google.genai import types as genai_types
# Import specific exceptions from google.api_core
from google.api_core import exceptions as google_exceptions

from agentkit.core.interfaces.llm_client import BaseLlmClient, LlmResponse


class GoogleClient(BaseLlmClient):
    """LLM Client implementation for Google Gemini models."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the Google Gemini client.

        Args:
            api_key: Google API key. Defaults to GOOGLE_API_KEY env var.
        """
        # The new SDK handles API key via env var GOOGLE_API_KEY automatically
        # or via constructor argument if needed. We'll rely on env var for now.
        # If api_key is explicitly passed, we should use it.
        client_options = {}
        if api_key:
            client_options["api_key"] = api_key
        elif not os.getenv("GOOGLE_API_KEY"):
             raise ValueError("Google API key not provided or found in environment variables (GOOGLE_API_KEY).")

        # TODO: Add support for Vertex AI client initialization if needed via env vars
        # GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION

        self.client = genai.Client(**client_options)

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_fixed(1),
        retry=tenacity.retry_if_exception_type((
            google_exceptions.ResourceExhausted, # Rate limits
            google_exceptions.InternalServerError, # 500 errors
            google_exceptions.ServiceUnavailable, # 503 errors
            google_exceptions.DeadlineExceeded, # Timeout on Google's side
            google_exceptions.Aborted, # Concurrency issues
            google_exceptions.Unknown, # Generic server error
        )),
        reraise=True # Reraise the exception if retries fail
    )
    async def _call_google_api(
        self,
        model_name: str,
        contents_payload: List[Dict[str, Any]],
        generation_config_obj: genai_types.GenerationConfig,
        timeout: Optional[float]
    ) -> Any:
        """Internal helper to make the actual API call with retry logic."""
        request_options = {}
        if timeout is not None:
            request_options['timeout'] = timeout

        return await self.client.aio.models.generate_content(
            model=model_name,
            contents=contents_payload,
            config=generation_config_obj,
            request_options=request_options # Pass timeout via request_options
        )

    async def generate(
        self,
        prompt: str, # Changed back to prompt: str
        model: Optional[str] = "gemini-pro", # Default model
        stop_sequences: Optional[List[str]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None, # Called max_output_tokens in Gemini
        timeout: Optional[float] = 60.0, # Default timeout in seconds
        **kwargs: Any
    ) -> LlmResponse:
        """
        Generates text based on a prompt string using the Google Gemini API.

        Args:
            prompt: The input prompt string for the LLM.
            model: The specific model identifier to use (e.g., "gemini-pro", "gemini-1.5-pro-latest").
            stop_sequences: List of sequences to stop generation at.
            temperature: Sampling temperature.
            max_tokens: Maximum number of tokens (output tokens) to generate.
            timeout: Optional request timeout in seconds (default: 60.0).
            **kwargs: Additional arguments for the Gemini API (e.g., top_p, top_k, system_prompt).

        Returns:
            An LlmResponse object containing the generated content and metadata.
        """
        try:
            # 1. Prepare contents structure based on the input prompt string.
            #    This matches the structure required by the Gemini API for text input.
            contents_payload = [{"parts": [{"text": prompt}]}]

            # 2. Prepare GenerationConfig with standard parameters.
            system_prompt = kwargs.get("system_prompt") # Get system prompt if passed via kwargs
            config_params = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "stop_sequences": stop_sequences,
                "top_p": kwargs.get("top_p"),
                "top_k": kwargs.get("top_k"),
                "system_instruction": system_prompt,
                # Note: OMITTING tool/func related keys like 'automatic_function_calling',
                # 'tools', 'tool_config' due to previous SDK inconsistency issues.
            }
            # Filter out None values from the standard generation parameters
            filtered_generation_config_params = {
                k: v for k, v in config_params.items() if v is not None
            }
            # Omit 'system_instruction' if it's None, as it might cause issues if passed as None
            if "system_instruction" in filtered_generation_config_params and filtered_generation_config_params["system_instruction"] is None:
                 del filtered_generation_config_params["system_instruction"]

            # Create the GenerationConfig object
            generation_config_obj = genai_types.GenerationConfig(**filtered_generation_config_params)

            # 3. Call the internal helper method with retry logic
            model_name_with_prefix = f"models/{model}"
            response = await self._call_google_api(
                model_name=model_name_with_prefix,
                contents_payload=contents_payload,
                generation_config_obj=generation_config_obj,
                timeout=timeout
            )

            # 4. Map the successful response to LlmResponse
            # Check for blocked content first
            prompt_feedback = getattr(response, 'prompt_feedback', None)
            if prompt_feedback and getattr(prompt_feedback, 'block_reason', None):
                block_reason = getattr(prompt_feedback, 'block_reason', None)
                blocked_content = f"Blocked: {block_reason.name if block_reason else 'Unknown Reason'}"
                return LlmResponse(
                    content=blocked_content,
                    model_used=model,
                    usage_metadata=None, # No usage data for blocked prompts
                    finish_reason="safety", # Set finish reason to safety
                    error=None,
                )

            # If not blocked, proceed to extract content and metadata
            # Determine finish reason
            finish_reason = "unknown"
            if response.candidates:
                raw_finish_reason = getattr(response.candidates[0], 'finish_reason', 'unknown')
                finish_reason = str(raw_finish_reason).lower()

            # Get usage metadata
            usage_metadata = getattr(response, 'usage_metadata', None)

            # Get content (should be safe now)
            content = response.text

            return LlmResponse(
                content=content,
                model_used=model,
                usage_metadata=usage_metadata, # Use calculated value
                finish_reason=finish_reason, # Use calculated value
                error=None,
            )
        # Catch specific Google API errors first
        except (
            google_exceptions.InvalidArgument,
            google_exceptions.PermissionDenied,
            google_exceptions.ResourceExhausted,
            google_exceptions.InternalServerError,
            google_exceptions.ServiceUnavailable,
            # Add other specific exceptions as needed
        ) as e:
            error_type = type(e).__name__
            return LlmResponse(
                content="",
                model_used=model,
                error=f"Google API error ({error_type}): {str(e)}",
            )
        # Catch any other unexpected errors
        except Exception as e:
            return LlmResponse(
                content="",
                model_used=model,
                error=f"An unexpected error occurred: {str(e)}",
            )
