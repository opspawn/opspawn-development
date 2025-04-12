"""Abstract base class for long-term memory interfaces."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class BaseLongTermMemory(ABC):
    """
    Abstract base class for agent long-term memory systems.

    Defines the core methods for adding memories and searching for relevant
    memories based on a query.
    """

    @abstractmethod
    async def add_memory(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Adds a piece of text memory to the long-term store.

        Args:
            text: The text content of the memory to add.
            metadata: Optional dictionary of metadata associated with the memory.
        """
        pass

    @abstractmethod
    async def search_memory(
        self, query: str, n_results: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Searches the long-term memory for relevant text based on the query.

        Args:
            query: The text query to search for.
            n_results: The maximum number of relevant memories to return.

        Returns:
            A list of tuples, where each tuple contains the retrieved memory
            text and its relevance score (higher is better, typically 0.0-1.0,
            though raw distances might be returned by some implementations).
            Returns an empty list if no relevant memories are found.
        """
        pass

    # Potential future methods (consider for post-MVP):
    # @abstractmethod
    # async def clear_memory(self) -> None:
    #     """Clears all memories from the store."""
    #     pass

    # @abstractmethod
    # async def delete_memory(self, memory_id: str) -> None:
    #     """Deletes a specific memory by its ID."""
    #     pass
