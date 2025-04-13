import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock

# Import the client AFTER potential patches are applied in fixtures/tests
from agentkit.llm_clients.google_client import GoogleClient
from agentkit.core.interfaces.llm_client import LlmResponse
# Import specific exceptions for retry testing
from google.api_core import exceptions as google_exceptions

# --- Fixtures ---

@pytest.fixture(autouse=True)
def mock_google_api_key_env(monkeypatch):
    """Fixture to provide a mock Google API key environment variable."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google_key_789")

# Use patch for the genai module and genai_types alias where they are imported
@pytest.fixture
def mock_genai_and_types():
    """Fixture to mock 'genai' and 'genai_types' used by GoogleClient."""
    # Patch both the main module and the aliased types import
    with patch('agentkit.llm_clients.google_client.genai') as mock_genai_module, \
         patch('agentkit.llm_clients.google_client.genai_types') as mock_genai_types_module:

        # Configure the mock Client class within the mocked genai module
        mock_client_instance = MagicMock()
        # Mock the async interface 'aio' and its 'models' attribute
        mock_client_instance.aio = MagicMock()
        mock_client_instance.aio.models = MagicMock()
        # Mock the async generate_content method
        mock_client_instance.aio.models.generate_content = AsyncMock() # Use AsyncMock
        mock_genai_module.Client.return_value = mock_client_instance

        # Configure the GenerationConfig mock on the *patched types module*
        # Add the __annotations__ attribute that the client code expects
        mock_config_constructor = MagicMock()
        mock_config_constructor.__annotations__ = {} # Add expected attribute
        mock_genai_types_module.GenerationConfig = mock_config_constructor
        # Mock Content and Part types used for constructing the 'contents' argument
        mock_genai_types_module.Content = MagicMock()
        mock_genai_types_module.Part = MagicMock()
        mock_genai_types_module.Part.from_text = MagicMock()

        # Yield both mocks
        yield mock_genai_module, mock_genai_types_module

@pytest.fixture
def google_client(mock_genai_and_types): # Depends on the mocked modules
    """Fixture for the GoogleClient instance, ensuring genai and types are mocked."""
    mock_genai, mock_genai_types = mock_genai_and_types
    # Reset the mock before creating the client instance for this test
    mock_genai.Client.reset_mock()
    mock_genai_types.GenerationConfig.reset_mock() # Also reset this mock
    client = GoogleClient()
    # Assert Client was called
    mock_genai.Client.assert_called_once_with()
    # Ensure the internal client is the mocked one
    assert client.client == mock_genai.Client.return_value

    # Reset the underlying mock method for each test
    mock_genai.Client.return_value.aio.models.generate_content.reset_mock()
    return client

# --- Test Cases ---

# xfail marker removed
@pytest.mark.asyncio
async def test_google_client_generate_success(google_client, mock_genai_and_types):
    """Tests successful generation using the Google client."""
    # Arrange
    mock_genai, mock_genai_types = mock_genai_and_types

    # Define the expected LlmResponse object that the client's generate method should return
    expected_model = "gemini-2.5-pro-exp-03-25" # Use the requested model
    expected_llm_response = LlmResponse(
        content="Generated Google text.",
        model_used=expected_model,
        usage_metadata={"prompt_token_count": 10, "candidates_token_count": 20, "total_token_count": 30},
        finish_reason="stop",
        error=None,
    )

    # Mock the SDK's generate_content method to return an object that, when processed by the client,
    # results in the expected_llm_response. We need a mock SDK response that has the necessary attributes
    # for the client code to extract the data.

    # Mock the SDK response structure
    mock_sdk_response = MagicMock()
    # Mock the .text attribute directly, as the client uses it
    type(mock_sdk_response).text = PropertyMock(return_value="Generated Google text.")
    # Mock candidates and finish_reason
    mock_candidate = MagicMock()
    type(mock_candidate).finish_reason = PropertyMock(return_value="STOP") # Use PropertyMock
    mock_sdk_response.candidates = [mock_candidate]
    # Mock usage metadata
    mock_sdk_response.usage_metadata = {"prompt_token_count": 10, "candidates_token_count": 20, "total_token_count": 30}
    # Ensure prompt_feedback is None for success case
    type(mock_sdk_response).prompt_feedback = PropertyMock(return_value=None)

    # Configure the mock aio.models.generate_content method to return this mock SDK response
    mock_genai.Client.return_value.aio.models.generate_content.return_value = mock_sdk_response

    # Define input prompt string
    prompt_text = "Explain Gemini."
    system_prompt = "Be concise."
    model = expected_model
    temperature = 0.8
    max_tokens = 200
    timeout_seconds = 55.0 # Specific timeout

    # Act
    response = await google_client.generate(
        prompt=prompt_text, # Pass prompt string directly
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        stop_sequences=["\n\n"],
        timeout=timeout_seconds, # Pass timeout
        top_p=0.9,
        system_prompt=system_prompt
    )

    # Assert - Compare individual fields instead of the whole object
    assert isinstance(response, LlmResponse)
    assert response.content == expected_llm_response.content, f"Content mismatch: Expected '{expected_llm_response.content}', got '{response.content}'"
    assert response.model_used == expected_llm_response.model_used
    assert response.usage_metadata == expected_llm_response.usage_metadata
    assert response.finish_reason == expected_llm_response.finish_reason
    assert response.error == expected_llm_response.error

    # Verify the mock API call to the async method
    mock_genai.Client.return_value.aio.models.generate_content.assert_awaited_once() # Use assert_awaited_once
    call_args, call_kwargs = mock_genai.Client.return_value.aio.models.generate_content.call_args

    assert call_kwargs["model"] == f"models/{model}" # Check prefix added

    # Verify the 'contents' argument structure passed to the SDK call
    expected_contents_payload = [{"parts": [{"text": prompt_text}]}]
    assert call_kwargs["contents"] == expected_contents_payload

    # Verify GenerationConfig was called correctly using the *patched types mock*
    mock_genai_types.GenerationConfig.assert_called_once()
    config_call_args, config_call_kwargs = mock_genai_types.GenerationConfig.call_args
    assert config_call_kwargs["temperature"] == temperature
    assert config_call_kwargs["max_output_tokens"] == max_tokens
    assert config_call_kwargs["stop_sequences"] == ["\n\n"]
    assert config_call_kwargs["top_p"] == 0.9
    assert config_call_kwargs["system_instruction"] == system_prompt
    # Assert the config instance passed to generate_content was the one returned by the mocked constructor
    assert call_kwargs["config"] == mock_genai_types.GenerationConfig.return_value
    # Verify timeout was passed via request_options
    assert call_kwargs["request_options"] == {'timeout': timeout_seconds}


# xfail marker removed
@pytest.mark.asyncio
async def test_google_client_generate_api_error(google_client, mock_genai_and_types):
    """Tests handling of Google API errors during generation."""
    # Arrange
    mock_genai, _ = mock_genai_and_types # Only need genai mock here
    # Configure the mock async generate_content method to raise a specific Google API error
    simulated_error_message = "Invalid argument provided."
    mock_genai.Client.return_value.aio.models.generate_content.side_effect = google_exceptions.InvalidArgument(simulated_error_message)

    prompt_text = "This will cause a Google error." # Use prompt string
    model = "gemini-pro" # Model name without prefix

    # Act
    response = await google_client.generate(prompt=prompt_text, model=model) # Pass prompt string

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == ""
    assert response.model_used == model
    # Assert the specific error format
    expected_error_msg = f"Google API error (InvalidArgument): {simulated_error_message}"
    # Note: The actual string representation might vary slightly depending on the exception details.
    # We check if the core message and type are present.
    assert "Google API error (InvalidArgument)" in response.error
    assert simulated_error_message in response.error
    assert response.usage_metadata is None
    assert response.finish_reason is None
    # Check the async mock was called (at least once, potentially more if retryable, though InvalidArgument isn't)
    assert mock_genai.Client.return_value.aio.models.generate_content.call_count >= 1


# xfail marker removed
@pytest.mark.asyncio
async def test_google_client_generate_blocked_prompt(google_client, mock_genai_and_types):
    """Tests handling of a blocked prompt response."""
    # Arrange
    mock_genai, _ = mock_genai_and_types # Only need genai mock here

    # Mock the response structure for a blocked prompt
    mock_sdk_response = MagicMock()
    # Mock prompt feedback structure
    mock_feedback = MagicMock()
    mock_block_reason = MagicMock()
    type(mock_block_reason).name = PropertyMock(return_value="SAFETY") # Set the name attribute
    type(mock_feedback).block_reason = PropertyMock(return_value=mock_block_reason)
    type(mock_sdk_response).prompt_feedback = PropertyMock(return_value=mock_feedback)
    # Ensure candidates is None or empty for blocked response
    mock_sdk_response.candidates = None
    # Ensure .text access raises an error or is None (client doesn't access it if blocked)
    type(mock_sdk_response).text = PropertyMock(side_effect=ValueError("Content blocked"))

    # Configure the mock async generate_content method
    mock_genai.Client.return_value.aio.models.generate_content.return_value = mock_sdk_response

    prompt_text = "A potentially unsafe prompt." # Use prompt string
    model = "gemini-pro" # Model name without prefix

    # Act
    response = await google_client.generate(prompt=prompt_text, model=model) # Pass prompt string

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == "Blocked: SAFETY"
    assert response.model_used == model
    assert response.error is None # Not an API error, but a safety block
    assert response.finish_reason == "safety" # Overridden due to block
    assert response.usage_metadata is None
    # Check the async mock was called
    mock_genai.Client.return_value.aio.models.generate_content.assert_awaited_once() # Use assert_awaited_once


# Use the mock_genai_and_types fixture which handles patching
def test_google_client_init_missing_key(monkeypatch, mock_genai_and_types):
    """Tests that initialization fails if the API key is missing."""
    mock_genai, _ = mock_genai_and_types
    # Arrange
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False) # Ensure env var is not set
    mock_genai.Client.reset_mock() # Reset mock before test

    # Act & Assert
    with pytest.raises(ValueError, match="Google API key not provided"):
        GoogleClient()
    # Ensure Client wasn't called without a key if env var is missing
    mock_genai.Client.assert_not_called()


# Use the mock_genai_and_types fixture which handles patching
def test_google_client_init_with_key_arg(mock_genai_and_types):
    """Tests initialization with the API key passed as an argument."""
    mock_genai, _ = mock_genai_and_types
    # Arrange
    api_key = "arg_google_key_123"
    mock_genai.Client.reset_mock() # Reset mock before test

    # Act
    client = GoogleClient(api_key=api_key)

    # Assert
    # Check that genai.Client was called with the arg key
    mock_genai.Client.assert_called_once_with(api_key=api_key)
    # Check internal client is the mocked one
    assert client.client == mock_genai.Client.return_value

# --- New Tests for Retry/Timeout ---

@pytest.mark.asyncio
async def test_google_client_retry_on_resource_exhausted(google_client, mock_genai_and_types):
    """Tests that the client retries on ResourceExhausted and eventually succeeds."""
    # Arrange
    mock_genai, mock_genai_types = mock_genai_and_types
    mock_generate_method = mock_genai.Client.return_value.aio.models.generate_content

    # Mock the successful response structure
    mock_sdk_response_success = MagicMock()
    type(mock_sdk_response_success).text = PropertyMock(return_value="Success after Google retry.")
    mock_candidate_success = MagicMock()
    type(mock_candidate_success).finish_reason = PropertyMock(return_value="STOP")
    mock_sdk_response_success.candidates = [mock_candidate_success]
    mock_sdk_response_success.usage_metadata = {"prompt_token_count": 1, "candidates_token_count": 1, "total_token_count": 2}
    type(mock_sdk_response_success).prompt_feedback = PropertyMock(return_value=None)

    # Configure side effect: fail twice with ResourceExhausted, then succeed
    mock_generate_method.side_effect = [
        google_exceptions.ResourceExhausted("Quota exceeded"),
        google_exceptions.ResourceExhausted("Quota still exceeded"),
        mock_sdk_response_success
    ]

    prompt = "Retry this Google call."
    model = "gemini-pro"

    # Act
    response = await google_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == "Success after Google retry."
    assert response.error is None
    assert response.model_used == model
    # Check that the API was called 3 times (2 failures + 1 success)
    assert mock_generate_method.call_count == 3

@pytest.mark.asyncio
async def test_google_client_retry_failure(google_client, mock_genai_and_types):
    """Tests that the client returns an error after exhausting retries."""
    # Arrange
    mock_genai, _ = mock_genai_and_types
    mock_generate_method = mock_genai.Client.return_value.aio.models.generate_content

    # Configure side effect: always fail with InternalServerError
    error_message = "Persistent server error"
    error_to_raise = google_exceptions.InternalServerError(error_message)
    mock_generate_method.side_effect = error_to_raise

    prompt = "This Google call will always fail."
    model = "gemini-pro"

    # Act
    response = await google_client.generate(prompt=prompt, model=model)

    # Assert
    assert isinstance(response, LlmResponse)
    assert response.content == ""
    assert response.model_used == model
    # Check that the error reflects the last raised exception
    expected_error_msg = f"Google API error (InternalServerError): {error_message}"
    assert "Google API error (InternalServerError)" in response.error
    assert error_message in response.error
    assert response.usage_metadata is None
    assert response.finish_reason is None
    # Check that the API was called 3 times (max retries)
    assert mock_generate_method.call_count == 3
