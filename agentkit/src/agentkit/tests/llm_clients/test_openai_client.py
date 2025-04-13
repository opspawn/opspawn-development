import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Import necessary types from the real library for type hinting and error simulation
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
from agentkit.llm_clients.openai_client import OpenAiClient
from agentkit.core.interfaces.llm_client import LlmResponse

# --- Fixtures ---

@pytest.fixture(autouse=True)
def mock_openai_api_key_env(monkeypatch):
    """Fixture to provide a mock OpenAI API key environment variable."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_key_123")

# Use patch for the AsyncOpenAI class where it's imported in the client code
@pytest.fixture
def mock_openai():
    """Fixture to mock the AsyncOpenAI class used by OpenAiClient."""
    with patch('agentkit.llm_clients.openai_client.AsyncOpenAI') as mock_async_openai_class:
        # Configure the mock instance that the mocked class will return
        mock_client_instance = AsyncMock() # Use AsyncMock for the instance
        # Mock the nested structure: client.chat.completions.create
        mock_client_instance.chat = AsyncMock()
        mock_client_instance.chat.completions = AsyncMock()
        mock_client_instance.chat.completions.create = AsyncMock() # Mock the create method
        mock_async_openai_class.return_value = mock_client_instance
        yield mock_async_openai_class # Yield the mocked class

@pytest.fixture
def openai_client(mock_openai): # Depends on the mocked AsyncOpenAI class
    """Fixture for the OpenAiClient instance, ensuring AsyncOpenAI is mocked."""
    # Reset the mock before creating the client instance for this test
    mock_openai.reset_mock()
    # Reset the nested mock method as well
    mock_openai.return_value.chat.completions.create.reset_mock()
    client = OpenAiClient()
    # Assert AsyncOpenAI was called
    mock_openai.assert_called_once_with(api_key="test_key_123", base_url=None)
    # Ensure the internal client is the mocked one
    assert client.client == mock_openai.return_value

    # --- IMPORTANT ---
    # Since retry logic is on _call_openai_api, we need to mock the *underlying*
    # self.client.chat.completions.create for retry/timeout tests.
    # The mock_openai fixture already does this. We'll use
    # mock_openai.return_value.chat.completions.create in the tests.
    # Reset the mock method specifically for each test run.
    mock_openai.return_value.chat.completions.create.reset_mock()
    return client

# --- Test Cases ---

@pytest.mark.asyncio
async def test_openai_client_generate_success(openai_client, mock_openai):
    """Tests successful generation using the OpenAI client."""
    # Arrange
    # The mock instance is mock_openai.return_value
    mock_client_instance = mock_openai.return_value

    # Mock the response structure based on OpenAI's ChatCompletion object
    # Use the imported Choice class or rely on MagicMock structure
    mock_choice = ChatCompletionChoice(
        index=0,
        message=ChatCompletionMessage(role="assistant", content="This is the generated text."),
        finish_reason="stop"
    )
    mock_usage = CompletionUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_completion = ChatCompletion(
        id="chatcmpl-123",
        choices=[mock_choice],
        created=1677652288,
        model="gpt-4", # Use the model name expected in the response
        object="chat.completion",
        usage=mock_usage
    )
    # Configure the mock create method on the client instance
    mock_client_instance.chat.completions.create.return_value = mock_completion

    prompt = "Tell me a story."
    model = "gpt-4"
    temperature = 0.5
    max_tokens = 150
    timeout_seconds = 30.0 # Specific timeout for this test
    system_prompt = "You are a tech expert."

    # Act
    response = await openai_client.generate(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stop_sequences=["\n"],
        system_prompt=system_prompt,
        timeout=timeout_seconds, # Pass timeout
        top_p=0.9
    )

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == "This is the generated text."
    assert response.model_used == "gpt-4" # Assert correct model
    assert response.error is None
    assert response.finish_reason == "stop"
    assert response.usage_metadata == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
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
    assert call_kwargs["top_p"] == 0.9
    assert call_kwargs["request_timeout"] == timeout_seconds # Verify timeout passthrough

@pytest.mark.asyncio
async def test_openai_client_generate_api_error(openai_client, mock_openai):
    """
    Tests handling of OpenAI API errors during generation.
    This covers non-retryable errors or errors after retries are exhausted.
    """
    # Arrange
    mock_client_instance = mock_openai.return_value
    # Simulate a non-retryable error (e.g., AuthenticationError, InvalidRequestError)
    # or a retryable one that persists after retries (tested separately).
    # Using a generic OpenAIError here for simplicity.
    error_to_raise = OpenAIError("Simulated API error")
    mock_client_instance.chat.completions.create.side_effect = error_to_raise

    prompt = "This will fail."
    model = "gpt-4"

    # Act
    response = await openai_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == ""
    assert response.model_used == model
    assert f"OpenAI API error: {error_to_raise}" in response.error # Check specific error
    assert response.usage_metadata is None
    assert response.finish_reason is None
    # The call should only happen once if the error is not retryable,
    # or after max retries if it was retryable (tested elsewhere).
    # For this generic test, assuming it was called (at least once).
    assert mock_client_instance.chat.completions.create.call_count >= 1

@pytest.mark.asyncio
async def test_openai_client_generate_unexpected_error(openai_client, mock_openai):
    """
    Tests handling of unexpected (non-OpenAIError) errors during generation.
    Retry logic should not apply here.
    """
    # Arrange
    mock_client_instance = mock_openai.return_value
    error_message = "Something went wrong unexpectedly"
    mock_client_instance.chat.completions.create.side_effect = Exception(error_message)

    prompt = "Another failure."
    model = "gpt-3.5-turbo"

    # Act
    response = await openai_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == ""
    assert response.model_used == model
    assert f"An unexpected error occurred: {error_message}" in response.error
    assert response.usage_metadata is None
    assert response.finish_reason is None
    # Should only be called once as non-OpenAIError exceptions aren't retried
    mock_client_instance.chat.completions.create.assert_awaited_once()

# Use the mock_openai fixture which handles patching
def test_openai_client_init_missing_key(monkeypatch, mock_openai):
    """Tests that initialization fails if the API key is missing."""
    # Arrange
    monkeypatch.delenv("OPENAI_API_KEY", raising=False) # Ensure env var is not set
    mock_openai.reset_mock() # Reset mock since it's autoused via env var fixture

    # Act & Assert
    with pytest.raises(ValueError, match="OpenAI API key not provided"):
        OpenAiClient()
    mock_openai.assert_not_called() # Ensure constructor wasn't called

# Use the mock_openai fixture which handles patching
def test_openai_client_init_with_key_arg(mock_openai):
    """Tests initialization with the API key passed as an argument."""
    # Arrange
    api_key = "arg_key_456"
    mock_openai.reset_mock() # Reset mock before test

    # Act
    client = OpenAiClient(api_key=api_key)

    # Assert
    assert client.api_key == api_key
    # Check that the *mocked* AsyncOpenAI class was called correctly
    mock_openai.assert_called_once_with(api_key=api_key, base_url=None)
    assert client.client == mock_openai.return_value

# --- New Tests for Retry/Timeout ---

@pytest.mark.asyncio
async def test_openai_client_retry_on_rate_limit(openai_client, mock_openai):
    """Tests that the client retries on RateLimitError and eventually succeeds."""
    # Arrange
    mock_client_instance = mock_openai.return_value
    mock_create_method = mock_client_instance.chat.completions.create

    # Mock the successful response structure
    mock_choice = ChatCompletionChoice(
        index=0,
        message=ChatCompletionMessage(role="assistant", content="Success after retry."),
        finish_reason="stop"
    )
    mock_usage = CompletionUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10)
    mock_success_completion = ChatCompletion(
        id="chatcmpl-retry", choices=[mock_choice], created=1677652299,
        model="gpt-4", object="chat.completion", usage=mock_usage
    )

    # Configure side effect: fail twice with RateLimitError, then succeed
    mock_create_method.side_effect = [
        RateLimitError("Rate limit exceeded", response=MagicMock(), body=None),
        RateLimitError("Rate limit exceeded again", response=MagicMock(), body=None),
        mock_success_completion
    ]

    prompt = "Retry this."
    model = "gpt-4"

    # Act
    response = await openai_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == "Success after retry."
    assert response.error is None
    assert response.model_used == "gpt-4"
    # Check that the API was called 3 times (2 failures + 1 success)
    assert mock_create_method.call_count == 3

@pytest.mark.asyncio
async def test_openai_client_retry_failure(openai_client, mock_openai):
    """Tests that the client returns an error after exhausting retries."""
    # Arrange
    mock_client_instance = mock_openai.return_value
    mock_create_method = mock_client_instance.chat.completions.create

    # Configure side effect: always fail with InternalServerError
    error_to_raise = InternalServerError("Server error", response=MagicMock(), body=None)
    mock_create_method.side_effect = error_to_raise

    prompt = "This will always fail."
    model = "gpt-4"

    # Act
    response = await openai_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == ""
    assert response.model_used == model
    # Check that the error reflects the last raised exception
    assert f"OpenAI API error: {error_to_raise}" in response.error
    assert response.usage_metadata is None
    assert response.finish_reason is None
    # Check that the API was called 3 times (max retries)
    assert mock_create_method.call_count == 3

# Use the mock_openai fixture which handles patching
def test_openai_client_init_with_base_url(mock_openai):
    """Tests initialization with a custom base URL."""
    # Arrange
    base_url = "http://localhost:8080/v1"
    api_key_from_env = "test_key_123" # From mock_openai_api_key_env
    mock_openai.reset_mock() # Reset mock before test

    # Act
    client = OpenAiClient(base_url=base_url) # Relies on env var fixture for key

    # Assert
    assert client.api_key == api_key_from_env # From fixture
    # Check that the *mocked* AsyncOpenAI class was called correctly
    mock_openai.assert_called_once_with(api_key=api_key_from_env, base_url=base_url)
    assert client.client == mock_openai.return_value # Check internal client
