import os
import asyncio
import functools
from typing import Dict, Any, Optional, List
import google.genai as genai # Changed import
from google.genai import types as genai_types # Use alias for types

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

    async def generate(
        self,
        prompt: str, # Changed back to prompt: str
        model: Optional[str] = "gemini-pro", # Default model
        stop_sequences: Optional[List[str]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None, # Called max_output_tokens in Gemini
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
            **kwargs: Additional arguments for the Gemini API (e.g., top_p, top_k, system_prompt).

        Returns:
            An LlmResponse object containing the generated content and metadata.
        """
        try:
            # Convert the prompt string into the required format for the SDK
            # For simple prompts, just pass the string directly.
            # For more complex interactions (multi-turn), this client might need enhancement
            # or users should use the underlying SDK directly.
            input_content = prompt

            # 2. Prepare GenerationConfig with ONLY standard parameters known to be valid
            system_prompt = kwargs.get("system_prompt") # Get system prompt if passed via kwargs

            # Standard generation parameters ONLY
            generation_config_params = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "stop_sequences": stop_sequences,
                "top_p": kwargs.get("top_p"), # Use get to avoid error if not passed
                "top_k": kwargs.get("top_k"), # Use get to avoid error if not passed
                "system_instruction": system_prompt,
            }
            # Filter out None values for GenerationConfig
            filtered_generation_config_params = {
                k: v for k, v in generation_config_params.items() if v is not None
            }
            generation_config_obj = genai_types.GenerationConfig(**filtered_generation_config_params)

            # 2. Prepare GenerationConfig, including system_prompt and other kwargs
            system_prompt = kwargs.pop("system_prompt", None) # Extract system prompt explicitly if passed via kwargs
            config_params = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "stop_sequences": stop_sequences,
                "top_p": kwargs.get("top_p"), # Keep top_p/top_k in kwargs for filtering below
                "top_k": kwargs.get("top_k"),
                "system_instruction": system_prompt, # Add system instruction here
                # Pass through any other valid GenerationConfig kwargs directly from input kwargs
                # Include potential 'tools' and 'tool_config' from kwargs here
                **kwargs
            }
            # Filter out None values AND ensure keys are valid for GenerationConfig
            # This prevents passing unexpected kwargs that might cause issues.
            valid_config_keys = genai_types.GenerationConfig.__annotations__.keys()
            filtered_config_params = {
                k: v for k, v in config_params.items() if v is not None and k in valid_config_keys
            }

            # 2. Prepare GenerationConfig, including standard params. Omit tool/func config for now.
            system_prompt = kwargs.get("system_prompt") # Get system prompt if passed via kwargs
            config_params = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "stop_sequences": stop_sequences,
                "top_p": kwargs.get("top_p"),
                "top_k": kwargs.get("top_k"),
                "system_instruction": system_prompt,
                # OMITTING tool/func related keys for now due to SDK inconsistency
                # "automatic_function_calling": genai_types.AutomaticFunctionCallingConfig(disable=True),
                # "tools": None,
                # "tool_config": None,
            }
            # Filter out None values from the standard generation parameters
            filtered_generation_config_params = {
                k: v for k, v in generation_config_params.items() if v is not None
            }
            # Omit 'system_instruction' if it's None, as it might cause issues if passed as None
            if "system_instruction" in filtered_generation_config_params and filtered_generation_config_params["system_instruction"] is None:
                 del filtered_generation_config_params["system_instruction"]


            # 3. Call the SYNCHRONOUS generate_content method in a separate thread.
            #    Pass configuration parameters directly as keyword arguments,
            #    instead of using a GenerationConfig object.
            sync_generate_content = functools.partial(
                self.client.models.generate_content, # Use sync client method
                model=f"models/{model}",
                contents=input_content,
                **filtered_generation_config_params # Unpack filtered standard params directly
            )
            response = await asyncio.to_thread(sync_generate_content)
            # 4. Map the successful response to LlmResponse
            finish_reason = "unknown"
            if response.candidates:
                 # Assuming finish_reason is an enum or string directly accessible
                 raw_finish_reason = getattr(response.candidates[0], 'finish_reason', 'unknown')
                 # Simplify conversion: just lowercase the string representation
                 finish_reason = str(raw_finish_reason).lower()

            # 3. Map the successful response to LlmResponse, handling potential ValueError for blocked content
            try:
                content = response.text # Revert back to using .text attribute
                # Finish reason and usage metadata are already calculated above
                usage_metadata = getattr(response, 'usage_metadata', None) # Get usage metadata

                return LlmResponse(
                    content=content,
                    model_used=model,
                    usage_metadata=usage_metadata, # Use calculated value
                    finish_reason=finish_reason, # Use calculated value
                    error=None,
                )
            except ValueError:
                # Handle blocked prompt specifically
                block_reason = getattr(getattr(response, 'prompt_feedback', None), 'block_reason', None)
                blocked_content = f"Blocked: {block_reason.name if block_reason else 'Unknown Reason'}"
                return LlmResponse(
                    content=blocked_content,
                    model_used=model,
                    usage_metadata=None, # No usage data for blocked prompts
                    finish_reason="safety", # Set finish reason to safety
                    error=None,
                )
        # Removed incorrect StopCandidateException block
        except Exception as e:
            # Catch other potential errors (API errors, network issues, SDK internal errors, etc.)
            return LlmResponse(
                content="",
                model_used=model,
                error=f"Google Gemini API error: {str(e)}", # Explicitly convert e to string
            )
