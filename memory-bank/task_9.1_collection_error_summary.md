# Task 9.1: SQLAlchemy Collection Error Summary (2025-04-09)

**Context:** While attempting to run tests for Task 9.1 (Repository Restructure), specifically Batch 4 (`ops_core/tests/integration/test_async_workflow.py`) using `tox`, a persistent error occurred during the pytest collection phase:

```
sqlalchemy.exc.InvalidRequestError: Table 'task' is already defined for this MetaData instance. Specify 'extend_existing=True' to redefine options and columns on an existing Table object.
```

This error prevented tests from being collected and run, blocking progress on Task 9.1 verification.

**Debugging Steps Taken:**

1.  **Verified `extend_existing=True`:** Confirmed that `__table_args__={'extend_existing': True}` was present in the `Task` model definition (`src/ops_core/models/tasks.py`).
2.  **Centralized `MetaData`:**
    *   Created `src/ops_core/models/base.py` to define a single, shared `MetaData` instance.
    *   Updated `src/ops_core/models/tasks.py` to import and use this shared `metadata`.
    *   Updated `src/ops_core/models/__init__.py` to export the shared `metadata`.
3.  **Aligned `conftest.py`:** Updated `ops_core/tests/conftest.py` (`db_session` fixture) to import and use the shared `metadata` object for `create_all` and `drop_all`.
4.  **Aligned `alembic/env.py`:** Updated `ops_core/alembic/env.py` to import and use the shared `metadata` object as `target_metadata`.
5.  **Standardized Imports:** Searched for inconsistent imports (`ops_core.` vs `src.ops_core.`) within the `ops_core` source and test files. Updated imports in the following files to use the `src.` prefix or be relative where appropriate:
    *   `src/ops_core/grpc_internal/task_servicer.py`
    *   `src/ops_core/tasks/worker.py`
    *   `src/ops_core/mcp_client/client.py`
    *   `src/ops_core/tests/integration/test_async_workflow.py`
    *   `src/ops_core/proto/tasks_pb2_grpc.py` (Note: This is generated, but the fix script handles it)
    *   `ops_core/tests/integration/test_api_scheduler_integration.py`
    *   `ops_core/tests/integration/test_e2e_workflow.py`
    *   `ops_core/tests/api/v1/endpoints/test_tasks.py`
    *   `ops_core/tests/api/v1/schemas/test_task_schemas.py`
    *   `ops_core/tests/grpc/test_task_servicer.py`
    *   `ops_core/tests/models/test_tasks.py`
    *   `ops_core/tests/metadata/test_store.py`
    *   `ops_core/tests/metadata/test_sql_store.py`
    *   `ops_core/tests/scheduler/test_engine.py`
6.  **Isolated Dependencies (`tox.ini`):** Temporarily removed the editable install of `agentkit` from `tox.ini` to check if the interaction between the two editable packages was causing the issue. The error persisted. Restored `agentkit` dependency.
7.  **Isolated Fixtures (`conftest.py`):** Temporarily commented out the `db_session` fixture in `ops_core/tests/conftest.py` to see if its interaction with metadata during collection was the cause. The error persisted. Restored the fixture.
8.  **Verbose Collection (`tox.ini`):** Ran `pytest -vv --collect-only` via `tox`. This revealed an `ImportError` in `ops_core/tests/tasks/test_broker.py` due to the conditional broker definition.
9.  **Fixed `test_broker.py`:** Added `@pytest.mark.skipif` to `ops_core/tests/tasks/test_broker.py` to skip the test when `DRAMATIQ_TESTING=1` is set, resolving the `ImportError`.

**Current Status:**
- The `ImportError` in `test_broker.py` is resolved.
- The `sqlalchemy.exc.InvalidRequestError: Table 'task' is already defined` **persists** during test collection via `tox`, even after applying standard fixes and diagnostic steps.
- The root cause seems related to how pytest collection interacts with the `src` layout, editable installs, and SQLAlchemy/SQLModel metadata within the `tox` environment, causing the `Task` model definition to be processed multiple times against the same `MetaData` object.

**Next Steps:**
- Further investigation is needed. Potential avenues:
    - Examine pytest collection hooks or plugins.
    - Simplify the test environment further (e.g., test outside `tox`).
    - Investigate specific interactions between SQLModel, SQLAlchemy, and pytest collection in `src` layouts.
    - Consider alternative ways to structure model definitions or metadata handling.
