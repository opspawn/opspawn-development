"""Unit tests for ChromaLongTermMemory."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from agentkit.memory.long_term.chroma_memory import ChromaLongTermMemory

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_chromadb_client():
    """Fixture for a mocked ChromaDB PersistentClient."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    return mock_client, mock_collection


@patch("agentkit.memory.long_term.chroma_memory.chromadb.PersistentClient")
async def test_chroma_ltm_initialization(mock_persistent_client, mock_chromadb_client):
    """Test successful initialization and collection creation."""
    mock_client, mock_collection = mock_chromadb_client
    mock_persistent_client.return_value = mock_client

    persist_dir = "/fake/path"
    collection_name = "test_collection"

    ltm = ChromaLongTermMemory(
        persist_directory=persist_dir, collection_name=collection_name
    )

    # Trigger collection creation by calling a method that uses it
    await ltm.add_memory("test memory")

    mock_persistent_client.assert_called_once_with(path=persist_dir)
    # Use asyncio.to_thread for the sync call inside the async wrapper
    await asyncio.sleep(0) # Allow thread to run
    mock_client.get_or_create_collection.assert_called_once_with(name=collection_name)
    assert ltm._collection is mock_collection


@patch("agentkit.memory.long_term.chroma_memory.chromadb.PersistentClient")
async def test_chroma_ltm_add_memory_success(mock_persistent_client, mock_chromadb_client):
    """Test successfully adding a memory."""
    mock_client, mock_collection = mock_chromadb_client
    mock_persistent_client.return_value = mock_client

    ltm = ChromaLongTermMemory()
    # Pre-populate the collection mock
    ltm._collection = mock_collection

    text_to_add = "This is a test memory."
    metadata_to_add = {"source": "test"}

    # Mock the collection's add method (which runs in a thread)
    mock_collection.add = MagicMock()

    await ltm.add_memory(text=text_to_add, metadata=metadata_to_add)

    # Check that collection.add was called via asyncio.to_thread
    await asyncio.sleep(0) # Allow thread to run
    mock_collection.add.assert_called_once()
    # Check args - ID is generated internally, so we check others
    call_args, call_kwargs = mock_collection.add.call_args
    assert call_kwargs.get("documents") == [text_to_add]
    assert call_kwargs.get("metadatas") == [metadata_to_add]
    assert isinstance(call_kwargs.get("ids"), list)
    assert len(call_kwargs.get("ids")[0]) == 32 # UUID hex


@patch("agentkit.memory.long_term.chroma_memory.chromadb.PersistentClient")
async def test_chroma_ltm_add_memory_empty_text(mock_persistent_client, mock_chromadb_client):
    """Test that adding empty text is skipped."""
    mock_client, mock_collection = mock_chromadb_client
    mock_persistent_client.return_value = mock_client

    ltm = ChromaLongTermMemory()
    ltm._collection = mock_collection
    mock_collection.add = MagicMock()

    await ltm.add_memory(text="")

    await asyncio.sleep(0)
    mock_collection.add.assert_not_called()


@patch("agentkit.memory.long_term.chroma_memory.chromadb.PersistentClient")
async def test_chroma_ltm_add_memory_unsupported_metadata(mock_persistent_client, mock_chromadb_client):
    """Test that unsupported metadata types are sanitized."""
    mock_client, mock_collection = mock_chromadb_client
    mock_persistent_client.return_value = mock_client

    ltm = ChromaLongTermMemory()
    ltm._collection = mock_collection
    mock_collection.add = MagicMock()

    metadata_to_add = {"valid": "string", "invalid": ["list"], "valid_num": 123}
    expected_metadata = {"valid": "string", "valid_num": 123}

    await ltm.add_memory(text="metadata test", metadata=metadata_to_add)

    await asyncio.sleep(0)
    mock_collection.add.assert_called_once()
    call_args, call_kwargs = mock_collection.add.call_args
    assert call_kwargs.get("metadatas") == [expected_metadata]


@patch("agentkit.memory.long_term.chroma_memory.chromadb.PersistentClient")
async def test_chroma_ltm_search_memory_success(mock_persistent_client, mock_chromadb_client):
    """Test successfully searching memory."""
    mock_client, mock_collection = mock_chromadb_client
    mock_persistent_client.return_value = mock_client

    ltm = ChromaLongTermMemory()
    ltm._collection = mock_collection

    query = "find test memory"
    n_results = 2
    mock_query_results = {
        "ids": [["id1", "id2"]],
        "documents": [["memory one", "memory two"]],
        "metadatas": [[{"src": "a"}, {"src": "b"}]],
        "distances": [[0.1, 0.2]],
    }
    # Mock the collection's query method (which runs in a thread)
    mock_collection.query = MagicMock(return_value=mock_query_results)

    results = await ltm.search_memory(query=query, n_results=n_results)

    await asyncio.sleep(0) # Allow thread to run
    mock_collection.query.assert_called_once_with(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "distances"],
    )
    assert results == [("memory one", 0.1), ("memory two", 0.2)]


@patch("agentkit.memory.long_term.chroma_memory.chromadb.PersistentClient")
async def test_chroma_ltm_search_memory_no_results(mock_persistent_client, mock_chromadb_client):
    """Test searching memory when no results are found."""
    mock_client, mock_collection = mock_chromadb_client
    mock_persistent_client.return_value = mock_client

    ltm = ChromaLongTermMemory()
    ltm._collection = mock_collection

    query = "find nothing"
    mock_query_results = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }
    mock_collection.query = MagicMock(return_value=mock_query_results)

    results = await ltm.search_memory(query=query)

    await asyncio.sleep(0)
    mock_collection.query.assert_called_once()
    assert results == []


@patch("agentkit.memory.long_term.chroma_memory.chromadb.PersistentClient")
async def test_chroma_ltm_search_memory_empty_query(mock_persistent_client, mock_chromadb_client):
    """Test searching memory with an empty query."""
    mock_client, mock_collection = mock_chromadb_client
    mock_persistent_client.return_value = mock_client

    ltm = ChromaLongTermMemory()
    ltm._collection = mock_collection
    mock_collection.query = MagicMock()

    results = await ltm.search_memory(query="")

    await asyncio.sleep(0)
    mock_collection.query.assert_not_called()
    assert results == []


@patch("agentkit.memory.long_term.chroma_memory.chromadb.PersistentClient")
async def test_chroma_ltm_search_memory_query_error(mock_persistent_client, mock_chromadb_client):
    """Test searching memory when the query raises an exception."""
    mock_client, mock_collection = mock_chromadb_client
    mock_persistent_client.return_value = mock_client

    ltm = ChromaLongTermMemory()
    ltm._collection = mock_collection

    # Mock query to raise an exception when called via to_thread
    mock_collection.query = MagicMock(side_effect=RuntimeError("DB error"))

    results = await ltm.search_memory(query="trigger error")

    await asyncio.sleep(0)
    mock_collection.query.assert_called_once()
    assert results == [] # Should return empty list on error
