# Plan: Refactor Dramatiq Actor Location (Task 7.2 - Idea 3)

**Date:** 2025-04-13

**Objective:** Resolve Dramatiq worker CLI invocation issues (`ActorNotFound` error after "Delay Imports" attempt) by moving the actor definition and its implementation logic out of the complex `ops-core/src/ops_core/scheduler/engine.py` module into a dedicated file.

**Rationale:** Defining the actor in a simpler, dedicated module (`actors.py`) that is directly imported by the worker (`worker.py`) might improve Dramatiq's actor discovery mechanism across processes during CLI startup, avoiding the issues seen when the actor was defined within the heavily-imported `engine.py`.

**Steps:**

1.  **Create New File:**
    *   Create a new file: `ops-core/src/ops_core/tasks/actors.py`.

2.  **Move Actor Implementation & Helpers to `actors.py`:**
    *   Cut the following functions and class definition from `ops-core/src/ops_core/scheduler/engine.py` and paste them into `ops-core/src/ops_core/tasks/actors.py`:
        *   `_execute_agent_task_actor_impl`
        *   `_run_agent_task_logic`
        *   `get_llm_client`
        *   `get_long_term_memory`
        *   `get_planner`
        *   `DefaultSecurityManager` class
    *   Move the `AGENT_EXECUTION_TIMEOUT` constant to `actors.py`.
    *   Add all necessary imports to the top of `actors.py` to support the moved code. Ensure correct relative paths (e.g., `from ..dependencies import ...`, `from ..models.tasks import ...`).

3.  **Move Actor Definition to `actors.py`:**
    *   Cut the `execute_agent_task_actor` definition (the `@dramatiq.actor(...)` decorator block) from `ops-core/src/ops_core/scheduler/engine.py` and paste it into `ops-core/src/ops_core/tasks/actors.py`, ensuring it correctly wraps the moved `_execute_agent_task_actor_impl` function.

4.  **Update `worker.py`:**
    *   Modify `ops-core/src/ops_core/tasks/worker.py`:
        *   Change the import `from ops_core.scheduler import engine` to `from . import actors`.
        *   Update associated log messages to refer to the `actors` module import.

5.  **Update `engine.py`:**
    *   Modify `ops-core/src/ops_core/scheduler/engine.py`:
        *   Remove the functions, class, and constant moved in Step 2 & 3.
        *   Remove imports that are no longer needed directly in `engine.py`. Keep only those required by `InMemoryScheduler`.
        *   Add a new import at the top: `from ops_core.tasks.actors import execute_agent_task_actor`.
        *   Verify that the `InMemoryScheduler.submit_task` method now uses the imported `execute_agent_task_actor.send()`.

**Visual Plan (Mermaid Diagram):**

```mermaid
graph TD
    subgraph ops-core/src/ops_core/scheduler/engine.py (Before)
        A[InMemoryScheduler] --> B(execute_agent_task_actor @dramatiq.actor)
        B --> C(_execute_agent_task_actor_impl)
        C --> D(_run_agent_task_logic)
        D --> E[Helper Functions/Classes]
        E --> F[Imports]
    end

    subgraph ops-core/src/ops_core/tasks/worker.py (Before)
        G[Worker Startup] --> H{Import engine.py}
        H --> B
    end

    subgraph ops-core/src/ops_core/tasks/actors.py (After - New File)
        style I fill:#cfc,stroke:#333,stroke-width:2px
        I(execute_agent_task_actor @dramatiq.actor) --> J(_execute_agent_task_actor_impl)
        J --> K(_run_agent_task_logic)
        K --> L[Helper Functions/Classes]
        L --> M[Imports]
    end

    subgraph ops-core/src/ops_core/scheduler/engine.py (After)
        style N fill:#f9f,stroke:#333,stroke-width:2px
        N[InMemoryScheduler] -- imports --> I
        N -- calls .send() --> I
    end

    subgraph ops-core/src/ops_core/tasks/worker.py (After)
        style O fill:#ccf,stroke:#333,stroke-width:2px
        O[Worker Startup] --> P{Import actors.py}
        P --> I
    end

    style A fill:#f9f,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style G fill:#ccf,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style B fill:#fcc,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style C fill:#fcc,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style D fill:#fcc,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style E fill:#fcc,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style F fill:#fcc,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style H fill:#fcc,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5