import os
from typing import Dict, Any, Optional, List

import tenacity
from openai import (
    AsyncOpenAI,
    OpenAIError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    APIStatusError,
)

from agentkit.core.interfaces.llm_client import BaseLlmClient, LlmResponse


class OpenAiClient(BaseLlmClient):
    """LLM Client implementation for OpenAI models."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initializes the OpenAI client.

        Args:
            api_key: OpenAI API key. Defaults to OPENAI_API_KEY env var.
            base_url: OpenAI API base URL. Defaults to OpenAI's default.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided or found in environment variables (OPENAI_API_KEY).")

        self.client = AsyncOpenAI(api_key=self.api_key, base_url=base_url)
        # TODO: Add more robust initialization if needed (e.g., custom httpx client)

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_fixed(1),
        retry=(
            tenacity.retry_if_exception_type((
                RateLimitError,
                APITimeoutError,
                APIConnectionError,
                InternalServerError,
            )) |
            # Retry on 5xx status errors specifically
            tenacity.retry_if_exception(lambda e: isinstance(e, APIStatusError) and e.status_code >= 500)
        ),
        reraise=True # Reraise the exception if retries fail
    )
    async def _call_openai_api(self, api_params: Dict[str, Any], timeout: Optional[float]) -> Any:
        """Internal helper to make the actual API call with retry logic."""
        return await self.client.chat.completions.create(
            **api_params,
            request_timeout=timeout # Pass timeout here
        )

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = "gpt-4o-mini", # Default model (changed to mini)
        stop_sequences: Optional[List[str]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = 60.0, # Default timeout in seconds
        **kwargs: Any
    ) -> LlmResponse:
        """
        Generates text based on a prompt using the OpenAI API.

        Args:
            prompt: The input prompt for the LLM.
            model: The specific model identifier to use (e.g., "gpt-4", "gpt-3.5-turbo").
            stop_sequences: List of sequences to stop generation at.
            temperature: Sampling temperature.
            max_tokens: Maximum number of tokens to generate.
            timeout: Optional request timeout in seconds (default: 60.0).
            **kwargs: Additional arguments for the OpenAI API (e.g., top_p, frequency_penalty).

        Returns:
            An LlmResponse object containing the generated content and metadata.
        """
        # 1. Format the prompt into the required 'messages' structure.
        #    Include system prompt if provided in kwargs.
        messages = []
        system_prompt = kwargs.pop("system_prompt", None) # Extract system_prompt from kwargs
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 2. Prepare API parameters
        api_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stop": stop_sequences,
            **kwargs, # Pass through any additional provider-specific args
        }
        # Add max_tokens only if it's specified, as OpenAI defaults might be preferred
        if max_tokens is not None:
            api_params["max_tokens"] = max_tokens

        try:
            # 3. Call the internal helper method with retry logic
            response = await self._call_openai_api(api_params, timeout)

            # 5. Map the successful response to LlmResponse
            choice = response.choices[0]
            content = choice.message.content or ""
            usage = response.usage
            usage_dict = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            } if usage else None

            return LlmResponse(
                content=content,
                model_used=response.model,
                usage_metadata=usage_dict,
                finish_reason=choice.finish_reason,
                error=None,
            )

        except OpenAIError as e:
            # 4. Handle potential OpenAIError exceptions.
            # 6. Map errors to LlmResponse.error.
            return LlmResponse(
                content="",
                model_used=model,
                error=f"OpenAI API error: {e}",
            )
        except Exception as e:
            # Catch any other unexpected errors during the process
            return LlmResponse(
                content="",
                model_used=model,
                error=f"An unexpected error occurred: {e}",
            )
