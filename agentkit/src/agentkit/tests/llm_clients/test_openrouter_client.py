import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Need OpenAI types and errors as OpenRouter uses the OpenAI SDK format
from openai import (
    OpenAIError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
    APIStatusError,
)
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice as ChatCompletionChoice
from openai.types.completion_usage import CompletionUsage

# Import the client AFTER potential patches are applied in fixtures/tests
from agentkit.llm_clients.openrouter_client import OpenRouterClient
from agentkit.core.interfaces.llm_client import LlmResponse

# --- Fixtures ---

@pytest.fixture(autouse=True)
def mock_openrouter_api_key_env(monkeypatch):
    """Fixture to provide a mock OpenRouter API key environment variable."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test_key_or_111")

# Use patch for the AsyncOpenAI class where it's imported in the client code
@pytest.fixture
def mock_openai_for_or():
    """Fixture to mock the AsyncOpenAI class used by OpenRouterClient."""
    # Target the import within the openrouter_client module
    with patch('agentkit.llm_clients.openrouter_client.AsyncOpenAI') as mock_async_openai_class:
        # Configure the mock instance that the mocked class will return
        mock_client_instance = AsyncMock() # Use AsyncMock for the instance
        # Mock the nested structure: client.chat.completions.create
        mock_client_instance.chat = AsyncMock()
        mock_client_instance.chat.completions = AsyncMock()
        mock_client_instance.chat.completions.create = AsyncMock() # Mock the create method
        mock_async_openai_class.return_value = mock_client_instance
        yield mock_async_openai_class # Yield the mocked class

@pytest.fixture
def openrouter_client(mock_openai_for_or): # Depends on the mocked AsyncOpenAI class
    """Fixture for the OpenRouterClient instance, ensuring AsyncOpenAI is mocked."""
    # Reset the mock before creating the client instance for this test
    mock_openai_for_or.reset_mock()
    # Reset the nested mock method as well
    mock_openai_for_or.return_value.chat.completions.create.reset_mock()
    client = OpenRouterClient()
    # Assert AsyncOpenAI was called with OpenRouter base URL and env var key
    mock_openai_for_or.assert_called_once_with(
        api_key="test_key_or_111",
        base_url=OpenRouterClient.DEFAULT_BASE_URL # Use class attribute for default
    )
    # Ensure the internal client is the mocked one
    assert client.client == mock_openai_for_or.return_value

    # Reset the underlying mock method for each test
    mock_openai_for_or.return_value.chat.completions.create.reset_mock()
    return client

# --- Test Cases ---

@pytest.mark.asyncio
async def test_openrouter_client_generate_success(openrouter_client, mock_openai_for_or):
    """Tests successful generation using the OpenRouter client."""
    # Arrange
    # The mock instance is mock_openai_for_or.return_value
    mock_client_instance = mock_openai_for_or.return_value

    # Mock the response structure based on OpenAI's ChatCompletion object
    mock_choice = ChatCompletionChoice(
        index=0,
        message=ChatCompletionMessage(role="assistant", content="Generated text via OpenRouter."),
        finish_reason="stop"
    )
    mock_usage = CompletionUsage(prompt_tokens=6, completion_tokens=12, total_tokens=18)
    mock_completion = ChatCompletion(
        id="or-chatcmpl-123",
        choices=[mock_choice],
        created=1677652300,
        model="anthropic/claude-3-haiku-20240307", # Use the model name expected in the response
        object="chat.completion",
        usage=mock_usage
    )
    # Configure the mock create method on the client instance
    mock_client_instance.chat.completions.create.return_value = mock_completion

    prompt = "Summarize this article."
    model = "anthropic/claude-3-haiku-20240307"
    temperature = 0.9
    max_tokens = 150
    timeout_seconds = 25.0 # Specific timeout
    system_prompt = "You are an OpenRouter expert."

    # Act
    response = await openrouter_client.generate(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stop_sequences=["\n"],
        system_prompt=system_prompt,
        timeout=timeout_seconds, # Pass timeout
        top_p=0.8
    )

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == "Generated text via OpenRouter."
    assert response.model_used == model
    assert response.error is None
    assert response.finish_reason == "stop"
    assert response.usage_metadata == {
        "prompt_tokens": 6,
        "completion_tokens": 12,
        "total_tokens": 18,
    }

    # Verify the mock API call
    mock_client_instance.chat.completions.create.assert_awaited_once()
    call_args, call_kwargs = mock_client_instance.chat.completions.create.call_args
    assert call_kwargs["model"] == model
    # Check messages structure including system prompt
    expected_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    assert call_kwargs["messages"] == expected_messages
    assert call_kwargs["temperature"] == temperature
    assert call_kwargs["max_tokens"] == max_tokens
    assert call_kwargs["stop"] == ["\n"]
    assert call_kwargs["top_p"] == 0.8
    assert call_kwargs["request_timeout"] == timeout_seconds # Verify timeout passthrough

@pytest.mark.asyncio
async def test_openrouter_client_generate_api_error(openrouter_client, mock_openai_for_or):
    """
    Tests handling of API errors (via OpenAI SDK) during generation.
    Covers non-retryable errors or errors after retries are exhausted.
    """
    # Arrange
    mock_client_instance = mock_openai_for_or.return_value
    error_to_raise = OpenAIError("Simulated OpenRouter API error")
    mock_client_instance.chat.completions.create.side_effect = error_to_raise

    prompt = "This will fail on OpenRouter."
    model = "google/gemini-pro" # Required model

    # Act
    response = await openrouter_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == ""
    assert response.model_used == model
    assert f"OpenRouter API error (via OpenAI SDK): {error_to_raise}" in response.error
    assert response.usage_metadata is None
    assert response.finish_reason is None
    assert mock_client_instance.chat.completions.create.call_count >= 1

@pytest.mark.asyncio
async def test_openrouter_client_generate_unexpected_error(openrouter_client, mock_openai_for_or):
    """
    Tests handling of unexpected (non-OpenAIError) errors during generation.
    Retry logic should not apply here.
    """
    # Arrange
    mock_client_instance = mock_openai_for_or.return_value
    error_message = "Something else failed"
    mock_client_instance.chat.completions.create.side_effect = Exception(error_message)

    prompt = "Trigger unexpected failure."
    model = "openai/gpt-4" # Required model

    # Act
    response = await openrouter_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == ""
    assert response.model_used == model
    assert f"An unexpected error occurred: {error_message}" in response.error
    assert response.usage_metadata is None
    assert response.finish_reason is None
    # Should only be called once
    mock_client_instance.chat.completions.create.assert_awaited_once()


# Use the mock_openai_for_or fixture which handles patching
def test_openrouter_client_init_missing_key(monkeypatch, mock_openai_for_or):
    """Tests that initialization fails if the API key is missing."""
    # Arrange
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False) # Ensure env var is not set
    mock_openai_for_or.reset_mock() # Reset mock since it's autoused via env var fixture

    # Act & Assert
    with pytest.raises(ValueError, match="OpenRouter API key not provided"):
        OpenRouterClient()
    mock_openai_for_or.assert_not_called() # Ensure constructor wasn't called

# Use the mock_openai_for_or fixture which handles patching
def test_openrouter_client_init_with_key_arg(mock_openai_for_or):
    """Tests initialization with the API key passed as an argument."""
    # Arrange
    api_key = "arg_or_key_222"
    mock_openai_for_or.reset_mock() # Reset mock before test

    # Act
    client = OpenRouterClient(api_key=api_key)

    # Assert
    assert client.api_key == api_key
    # Check that the *mocked* AsyncOpenAI class was called correctly
    mock_openai_for_or.assert_called_once_with(
        api_key=api_key,
        base_url=OpenRouterClient.DEFAULT_BASE_URL
    )
    assert client.client == mock_openai_for_or.return_value

# --- New Tests for Retry/Timeout ---

@pytest.mark.asyncio
async def test_openrouter_client_retry_on_rate_limit(openrouter_client, mock_openai_for_or):
    """Tests that the client retries on RateLimitError and eventually succeeds."""
    # Arrange
    mock_client_instance = mock_openai_for_or.return_value
    mock_create_method = mock_client_instance.chat.completions.create

    # Mock the successful response structure
    mock_choice = ChatCompletionChoice(
        index=0,
        message=ChatCompletionMessage(role="assistant", content="Success after OR retry."),
        finish_reason="stop"
    )
    mock_usage = CompletionUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10)
    mock_success_completion = ChatCompletion(
        id="or-chatcmpl-retry", choices=[mock_choice], created=1677652399,
        model="google/gemini-pro", object="chat.completion", usage=mock_usage
    )

    # Configure side effect: fail twice with RateLimitError, then succeed
    mock_create_method.side_effect = [
        RateLimitError("OR Rate limit exceeded", response=MagicMock(), body=None),
        RateLimitError("OR Rate limit exceeded again", response=MagicMock(), body=None),
        mock_success_completion
    ]

    prompt = "Retry this OR call."
    model = "google/gemini-pro" # Required

    # Act
    response = await openrouter_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == "Success after OR retry."
    assert response.error is None
    assert response.model_used == model
    # Check that the API was called 3 times (2 failures + 1 success)
    assert mock_create_method.call_count == 3

@pytest.mark.asyncio
async def test_openrouter_client_retry_failure(openrouter_client, mock_openai_for_or):
    """Tests that the client returns an error after exhausting retries."""
    # Arrange
    mock_client_instance = mock_openai_for_or.return_value
    mock_create_method = mock_client_instance.chat.completions.create

    # Configure side effect: always fail with InternalServerError
    error_to_raise = InternalServerError("OR Server error", response=MagicMock(), body=None)
    mock_create_method.side_effect = error_to_raise

    prompt = "This OR call will always fail."
    model = "openai/gpt-4" # Required

    # Act
    response = await openrouter_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == ""
    assert response.model_used == model
    # Check that the error reflects the last raised exception
    assert f"OpenRouter API error (via OpenAI SDK): {error_to_raise}" in response.error
    assert response.usage_metadata is None
    assert response.finish_reason is None
    # Check that the API was called 3 times (max retries)
    assert mock_create_method.call_count == 3

# Use the mock_openai_for_or fixture which handles patching
def test_openrouter_client_init_with_base_url(mock_openai_for_or):
    """Tests initialization with a custom base URL."""
    # Arrange
    base_url = "http://custom-openrouter-proxy/v1"
    api_key_from_env = "test_key_or_111" # From mock_openrouter_api_key_env
    mock_openai_for_or.reset_mock() # Reset mock before test

    # Act
    client = OpenRouterClient(base_url=base_url) # Relies on env var fixture for key

    # Assert
    assert client.api_key == api_key_from_env # From fixture
    # Check that the *mocked* AsyncOpenAI class was called correctly
    mock_openai_for_or.assert_called_once_with(
        api_key=api_key_from_env,
        base_url=base_url
    )
    assert client.client == mock_openai_for_or.return_value # Check internal client
