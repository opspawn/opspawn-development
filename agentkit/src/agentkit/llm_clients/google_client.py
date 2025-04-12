import os
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

            # 2. Prepare GenerationConfig, including system_prompt from kwargs
            system_prompt = kwargs.pop("system_prompt", None) # Extract system prompt
            config_params = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "stop_sequences": stop_sequences,
                "top_p": kwargs.get("top_p"),
                "top_k": kwargs.get("top_k"),
                "system_instruction": system_prompt, # Add system instruction here
                # Pass through any other valid GenerationConfig kwargs
                **{k: v for k, v in kwargs.items() if k in genai_types.GenerationConfig.__annotations__ and k != "system_instruction"} # Avoid duplicating system_instruction
            }
            # Filter out None values as SDK expects concrete values or omission
            filtered_config_params = {k: v for k, v in config_params.items() if v is not None}

            # 3. Call the async generate_content method
            # The new SDK's generate_content takes the prompt string directly in 'contents'
            # Pass configuration parameters directly as keyword arguments
            response = await self.client.aio.models.generate_content(
                model=f"models/{model}", # Models often need 'models/' prefix
                contents=input_content, # Pass the prompt string directly
                # generation_config=genai_types.GenerationConfig(**filtered_config_params), # Don't pass as object
                **filtered_config_params, # Unpack config params as kwargs
                # safety_settings=... # Can be added if needed
            )

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
