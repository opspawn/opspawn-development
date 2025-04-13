# PLANNING: Task 7.2 Debugging - Step 8: Delay Heavy Imports in Worker

**Date:** 2025-04-13

## 1. Goal

Resolve the Dramatiq worker invocation failure observed when starting the worker via the CLI (`dramatiq ops_core.tasks.worker`) or subprocesses (as seen in `test_dramatiq_worker.py` and live E2E tests). The primary hypothesis, supported by previous debugging and the successful minimal test case, is that heavy imports occurring during worker startup (specifically during the import of `ops_core.scheduler.engine`) cause excessive delays or initialization conflicts that prevent Dramatiq from properly processing tasks.

The goal is to modify the worker entry point and related modules to delay the loading of these heavy dependencies until they are actually needed *inside* the actor function execution context.

## 2. Background

- **Problem:** `dramatiq ops_core.tasks.worker` command hangs or fails to process messages. Debugging showed significant delays (~3-30s) during the `import ops_core.scheduler.engine` statement within `ops_core/tasks/worker.py`.
- **Minimal Test Success:** A minimal Flask/Dramatiq app where the broker was configured and the actor defined in the *same file* with minimal top-level imports worked correctly when invoked via `dramatiq app`.
- **Hypothesis:** The complex dependency graph loaded by `ops_core.scheduler.engine` (including Agentkit, DB Store, LLM Clients, etc.) interferes with Dramatiq's initialization when loaded at the module level during worker startup.

## 3. Proposed Changes (Idea 1: Delay Imports)

Modify the code to ensure only essential components for Dramatiq broker setup and actor *discovery* are loaded at the module level. All other dependencies required for actor *execution* will be imported locally within the actor function.

### 3.1. Target Files

-   `ops-core/src/ops_core/tasks/worker.py` (Worker Entry Point)
-   `ops-core/src/ops_core/scheduler/engine.py` (Contains Actor Logic & Heavy Imports)

### 3.2. Changes to `ops-core/src/ops_core/tasks/worker.py`

-   **Analyze Current Imports:** Review the existing top-level imports.
-   **Retain Essential Imports:** Keep only the imports necessary for Dramatiq to find the broker and the actor function signature:
    ```python
    # Keep: Imports related to broker setup (if any are directly here, though likely in broker.py)
    import ops_core.tasks.broker # Ensures broker is configured via dramatiq.set_broker()

    # Keep: Import the actor function itself so Dramatiq discovers it
    from ops_core.scheduler.engine import execute_agent_task_actor
    ```
-   **Remove/Comment Out Other Imports:** Any other top-level imports (especially those related to `engine` internals, logging setup specific to the full engine, etc.) should be removed or commented out if they aren't strictly required just for the `dramatiq` CLI tool to discover the `execute_agent_task_actor`.

### 3.3. Changes to `ops-core/src/ops_core/scheduler/engine.py`

-   **Analyze Current Top-Level Imports:** Identify all imports at the top of the file (e.g., `agentkit`, `SqlMetadataStore`, `OpsMcpClient`, LLM clients, config loaders, specific schemas, etc.).
-   **Identify Execution-Only Imports:** Determine which of these imports are solely used within the `execute_agent_task_actor` function or helper functions called *only* by it.
-   **Move Imports Inside Actor:** Relocate these identified execution-only imports to the *beginning* of the `execute_agent_task_actor` function definition.
    ```python
    # Example structure:
    # (Keep minimal top-level imports needed for class/function definitions if any)
    import dramatiq # Likely needed for the decorator
    # ... other minimal imports ...

    @dramatiq.actor(time_limit=3_600_000, max_retries=0) # Keep decorator
    def execute_agent_task_actor(task_id: str, agent_config_json: str):
        # <<< MOVE HEAVY/EXECUTION IMPORTS HERE >>>
        import asyncio
        from agentkit.core.agent import Agent
        # ... import agentkit planners, memory, tools ...
        from ops_core.metadata.sql_store import SqlMetadataStore # Or BaseMetadataStore if type hinting
        from ops_core.config.loader import get_config
        from ops_core.dependencies import get_mcp_client, get_db_session_factory # For creating instances
        # ... import LLM clients ...
        # ... import schemas needed only for execution ...
        from pydantic import ValidationError
        # ... etc ...

        # <<< ORIGINAL ACTOR LOGIC STARTS HERE >>>
        # Setup logging specific to the actor run?
        # Create instances using imported factories/classes
        # session_factory = get_db_session_factory()
        # async with session_factory() as session:
        #     store = SqlMetadataStore(session) # Pass session if needed by constructor
        #     mcp_client = get_mcp_client()
            # ... rest of the actor logic ...
    ```
-   **Handle Potential Circular Imports:** If moving imports causes circular dependency errors (e.g., module A imports B at top-level, B imports A inside a function), resolve them. This might involve further refactoring or using local imports carefully. Type hinting might require `from typing import TYPE_CHECKING` blocks or string forward references.

## 4. Testing and Verification Strategy

1.  **Environment Setup:**
    *   Ensure the main project's Docker services (Postgres, RabbitMQ) are running (`docker compose up -d`).
    *   Activate the appropriate Python environment where `ops-core` and its dependencies are installed.
2.  **Direct CLI Worker Test:**
    *   Run the worker directly from the CLI:
        ```bash
        dramatiq ops_core.tasks.worker
        ```
    *   Observe the startup logs. Check if the previous long delay is gone.
3.  **Send Test Message:**
    *   While the worker is running (in a separate terminal), use a script like `send_test_message_clean_env.py` (potentially adapting it slightly if needed) or manually enqueue a task via `dramatiq shell` or a simple Python script to send a message to the `execute_agent_task_actor`.
4.  **Verify Processing:**
    *   Observe the worker terminal logs. Confirm that the worker picks up the task and starts executing the actor logic (indicated by logs *inside* the `execute_agent_task_actor` function).
    *   Check for any new errors during execution, especially related to the moved imports.
5.  **Subprocess Test (Optional but Recommended):**
    *   If the direct CLI test works, re-run the `test_dramatiq_worker.py` script (or a simplified version) that invokes the worker via `subprocess.Popen`. Verify if it now passes.
6.  **Live E2E Test (Ultimate Goal):**
    *   If the above tests pass, attempt to run the full live E2E tests (`pytest -m e2e_live`) again to see if Task 7.2 is resolved.

## 5. Rollback Plan

-   Use Git to manage changes. If the delayed import strategy fails or introduces significant new problems, revert the changes using `git checkout -- <file>` or `git stash`.