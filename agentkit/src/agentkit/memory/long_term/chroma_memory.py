"""Implementation of long-term memory using ChromaDB."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.errors import InvalidDimensionException

from agentkit.core.interfaces.long_term_memory import BaseLongTermMemory

logger = logging.getLogger(__name__)


class ChromaLongTermMemory(BaseLongTermMemory):
    """
    Long-term memory implementation using ChromaDB.

    Stores text memories and allows searching based on semantic similarity.
    Uses chromadb's PersistentClient for local storage.
    """

    def __init__(
        self,
        persist_directory: str = "./.chroma_db",
        collection_name: str = "agent_memory",
    ):
        """
        Initializes the ChromaDB long-term memory store.

        Args:
            persist_directory: The directory to store ChromaDB data.
                               Defaults to './.chroma_db'.
            collection_name: The name of the ChromaDB collection to use.
                             Defaults to 'agent_memory'.
        """
        logger.info(
            f"Initializing ChromaDB client at path: {persist_directory}"
        )
        self._persist_directory = Path(persist_directory)
        self._collection_name = collection_name
        self._client = chromadb.PersistentClient(
            path=str(self._persist_directory)
        )
        self._collection: Optional[Collection] = None
        # Defer collection creation until first use to handle potential
        # async issues during initialization if needed, though PersistentClient
        # is typically synchronous.

    def _get_or_create_collection(self) -> Collection:
        """Gets or creates the ChromaDB collection."""
        if self._collection is None:
            try:
                logger.info(
                    f"Getting or creating ChromaDB collection: {self._collection_name}"
                )
                # Note: Default embedding function (all-MiniLM-L6-v2) will be used.
                self._collection = self._client.get_or_create_collection(
                    name=self._collection_name
                )
            except Exception as e:
                logger.error(f"Failed to get or create ChromaDB collection: {e}", exc_info=True)
                raise
        return self._collection

    async def add_memory(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Adds a piece of text memory to the ChromaDB collection.

        Uses asyncio.to_thread to run the synchronous ChromaDB operation.

        Args:
            text: The text content of the memory to add.
            metadata: Optional dictionary of metadata associated with the memory.
                      Note: Metadata values must be str, int, float, or bool.
        """
        if not text:
            logger.warning("Attempted to add empty memory text. Skipping.")
            return

        memory_id = uuid.uuid4().hex
        logger.debug(f"Adding memory with ID: {memory_id}")

        # Ensure metadata values are of supported types
        sanitized_metadata = None
        if metadata:
            sanitized_metadata = {
                k: v
                for k, v in metadata.items()
                if isinstance(v, (str, int, float, bool))
            }
            if len(sanitized_metadata) != len(metadata):
                logger.warning(
                    "Some metadata fields were removed due to unsupported types."
                )

        try:
            # Use asyncio.to_thread for synchronous ChromaDB operations
            collection = await asyncio.to_thread(self._get_or_create_collection)
            await asyncio.to_thread(
                collection.add,
                documents=[text],
                metadatas=[sanitized_metadata] if sanitized_metadata else None,
                ids=[memory_id],
            )
            logger.info(f"Successfully added memory ID: {memory_id}")
        except InvalidDimensionException as e:
             logger.error(f"ChromaDB dimension error adding memory: {e}. "
                          f"This might happen if the collection was created with a different embedding model.", exc_info=True)
             # Consider how to handle this - re-create collection? Raise specific error?
             raise # Re-raise for now
        except Exception as e:
            logger.error(f"Failed to add memory ID {memory_id} to ChromaDB: {e}", exc_info=True)
            # Decide on error handling: raise? return failure?
            raise # Re-raise for now

    async def search_memory(
        self, query: str, n_results: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Searches the ChromaDB collection for relevant text based on the query.

        Uses asyncio.to_thread to run the synchronous ChromaDB operation.
        Returns text and distance score (lower is better).

        Args:
            query: The text query to search for.
            n_results: The maximum number of relevant memories to return.

        Returns:
            A list of tuples, where each tuple contains the retrieved memory
            text and its distance score (lower means more similar).
            Returns an empty list if no relevant memories are found or an error occurs.
        """
        if not query:
            logger.warning("Attempted to search memory with empty query.")
            return []

        logger.debug(f"Searching memory with query: '{query[:50]}...'")
        try:
            # Use asyncio.to_thread for synchronous ChromaDB operations
            collection = await asyncio.to_thread(self._get_or_create_collection)
            results = await asyncio.to_thread(
                collection.query,
                query_texts=[query],
                n_results=n_results,
                include=["documents", "distances"], # Request documents and distances
            )

            # Process results: Chroma returns distances, lower is better.
            # We return (document, distance) tuples.
            processed_results: List[Tuple[str, float]] = []
            if results and results.get("documents") and results.get("distances"):
                # Ensure the lists exist and are not empty before accessing index 0
                docs_list = results["documents"]
                distances_list = results["distances"]
                if docs_list and distances_list:
                    docs = docs_list[0]
                    distances = distances_list[0]
                    if docs is not None and distances is not None and len(docs) == len(distances):
                        processed_results = list(zip(docs, distances))
                        logger.info(f"Found {len(processed_results)} relevant memories.")
                    else:
                        logger.error("ChromaDB query returned mismatched or None lists for documents and distances.")
                else:
                    logger.info("ChromaDB query returned no documents or distances.")


            return processed_results

        except InvalidDimensionException as e:
             logger.error(f"ChromaDB dimension error searching memory: {e}. "
                          f"This might happen if the collection was created with a different embedding model.", exc_info=True)
             return [] # Return empty on error
        except Exception as e:
            logger.error(f"Failed to search memory in ChromaDB: {e}", exc_info=True)
            return [] # Return empty list on error
