# Task 6.4: Implement `agentkit` Long-Term Memory MVP - Plan

**Date:** 2025-04-12

**Goal:** Implement a Minimum Viable Product (MVP) for long-term memory within `agentkit`, allowing agents to store and retrieve information across sessions using a vector database.

**Chosen Vector Database:** ChromaDB (Suitable for local development, easy setup).

## Implementation Steps

1.  **Add Dependencies:**
    *   Add `chromadb` to `agentkit/pyproject.toml` under `[project.optional-dependencies]`. Create a new optional dependency group, e.g., `long_term_memory`, or add it to `[test]` if appropriate for initial testing.
    *   Update `1-t/tox.ini` to install the new optional dependency group for relevant test environments.

2.  **Define Interface (`BaseLongTermMemory`):**
    *   Create a new interface file: `agentkit/src/agentkit/core/interfaces/long_term_memory.py`.
    *   Define an abstract base class `BaseLongTermMemory` with core methods:
        *   `add_memory(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None`: Adds a piece of text memory.
        *   `search_memory(self, query: str, n_results: int = 5) -> List[Tuple[str, float]]`: Searches memory for relevant text based on the query, returning text and similarity score.
        *   Potentially others like `clear_memory()`, `delete_memory()`, etc. (Consider for MVP scope).
    *   Ensure methods are `async` if the underlying implementation requires it.

3.  **Implement `ChromaLongTermMemory`:**
    *   Create implementation file: `agentkit/src/agentkit/memory/long_term/chroma_memory.py` (create `long_term` directory).
    *   Implement the `ChromaLongTermMemory` class inheriting from `BaseLongTermMemory`.
    *   **Initialization (`__init__`)**:
        *   Accept configuration parameters:
            *   `persist_directory`: Path for ChromaDB data.
            *   `collection_name`: Name for the Chroma collection.
        *   Initialize `chromadb.PersistentClient` with the `persist_directory`.
        *   Get or create the Chroma collection using `client.get_or_create_collection()`. Handle potential embedding function configuration if needed (default might suffice for MVP).
    *   **Implement `add_memory`**:
        *   Generate a unique ID for the memory entry (e.g., `uuid.uuid4().hex`).
        *   Use `collection.add()` to store the text, metadata (if provided), and ID.
    *   **Implement `search_memory`**:
        *   Use `collection.query()` with the `query_texts` and `n_results` parameters.
        *   Process the results to return the desired `List[Tuple[str, float]]` format (text and distance/score). Note: Chroma returns distances; decide if conversion to similarity score is needed.

4.  **Integrate into `Agent`:**
    *   Modify `agentkit/src/agentkit/core/agent.py::Agent.__init__`:
        *   Add an optional `long_term_memory: Optional[BaseLongTermMemory] = None` parameter.
        *   Store it as `self.long_term_memory`.
    *   Modify `Agent.run` (or relevant internal methods):
        *   Decide *when* to add memories (e.g., after each step, at the end of a run).
        *   Decide *when* to search memories (e.g., at the start of a run to augment context, before planning a step).
        *   For MVP, consider a simple approach:
            *   Add the final result/summary of the agent run to memory.
            *   Optionally, search memory at the beginning of `run` and add relevant results to the initial context/prompt.

5.  **Configuration (`ops-core`):**
    *   Update `ops_core/src/ops_core/scheduler/engine.py::_run_agent_task_logic`:
        *   Add logic to read configuration for long-term memory (e.g., from env vars like `AGENTKIT_LTM_PROVIDER`, `AGENTKIT_LTM_CHROMA_PATH`, `AGENTKIT_LTM_CHROMA_COLLECTION`).
        *   Conditionally instantiate the correct `BaseLongTermMemory` implementation (e.g., `ChromaLongTermMemory`) based on the provider config.
        *   Pass the instantiated LTM object to the `Agent` constructor.
    *   Update relevant documentation (`README.md` or config docs) about the new environment variables.

6.  **Unit Testing:**
    *   Create test file: `agentkit/src/agentkit/tests/memory/long_term/test_chroma_memory.py`.
    *   Write unit tests for `ChromaLongTermMemory`:
        *   Test initialization (creating directories/collections). Use `tmp_path` fixture.
        *   Test `add_memory`.
        *   Test `search_memory` (finding relevant results, handling no results).
        *   Mock `chromadb` client/collection interactions appropriately.
    *   Update `agentkit/src/agentkit/tests/core/test_agent.py`:
        *   Add tests verifying the agent interacts with the `long_term_memory` object (add/search) when provided. Mock the `BaseLongTermMemory` interface.

7.  **Documentation Updates:**
    *   Update `memory-bank/agentkit_overview.md` to describe the new long-term memory capability and `ChromaLongTermMemory` implementation.
    *   Update `memory-bank/activeContext.md` and `memory-bank/progress.md` to reflect the start and progress of Task 6.4.
    *   Update `TASK.md` to mark Task 6.4 as "In Progress" and add sub-tasks based on this plan.

8.  **Verification:**
    *   Run `tox -e py312` in the `1-t` directory to ensure all tests (including new ones) pass and the integration works within the combined environment.

## MVP Scope Considerations

-   **Memory Addition Strategy:** Start simple (e.g., add final agent output). More complex strategies (adding intermediate thoughts/steps) can be future enhancements.
-   **Memory Search Strategy:** Start simple (e.g., search at the beginning of a run). More complex strategies (searching before each planning step) can be future enhancements.
-   **Error Handling:** Basic error handling for DB interactions.
-   **Metadata:** Allow basic metadata storage, but complex filtering/querying based on metadata is likely out of scope for MVP.
-   **Embedding Model:** Use ChromaDB's default embedding model for simplicity. Configuration of different models can be a future enhancement.
