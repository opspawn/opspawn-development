# Task 9.1 (Batch 5) - Persistent `pika.exceptions.AMQPConnectionError` Debugging Summary

**Date:** 2025-04-09

**File:** `ops_core/tests/integration/test_e2e_workflow.py`

**Task:** Resolve test failures in Batch 5 (E2E tests) as part of Task 9.1 (Repository Restructure).

**Problem:**
Tests in `test_e2e_workflow.py` consistently fail with `assert 500 == 201`. The underlying cause, visible in the logs, is a `pika.exceptions.AMQPConnectionError: Connection refused` originating when `execute_agent_task_actor.send()` is called within `src/ops_core/scheduler/engine.py::InMemoryScheduler.submit_task`. This occurs despite the intention to use Dramatiq's `StubBroker` for testing, which should prevent real network connection attempts. The RabbitMQ Docker container is confirmed *not* to be running during these tests, which is expected when using `StubBroker`.

**Debugging Attempts & Results:**

1.  **Initial State:** Tests failed with `Connection refused`. Patching strategy involved patching `actor.send` in the `test_app_components` fixture.
2.  **Hypothesis:** Global `StubBroker` fixture in `conftest.py` (`set_stub_broker`) might not be running early enough, or the actor binds to the default broker at import time.
3.  **Attempt 1: Rely solely on global `StubBroker` fixture:**
    *   Removed the explicit patch on `actor.send` from `test_app_components`.
    *   Added assertions to verify `dramatiq.get_broker()` returns a `StubBroker` and that the message appears in its queue.
    *   **Result:** Failed. Still got `Connection refused`. The assertions checking the `StubBroker` queue failed because the error occurred before the message could be queued.
4.  **Attempt 2: Patch entire actor object:**
    *   Reverted Attempt 1 changes.
    *   Changed the patch target in `test_app_components` from `actor.send` to the actor object itself (`src.ops_core.scheduler.engine.execute_agent_task_actor`).
    *   **Result:** Failed. Still got `Connection refused`. Patching the actor object didn't prevent the underlying connection attempt triggered by calling `.send()` on the mock.
5.  **Attempt 3: Patch `StubBroker.enqueue_message` (Incorrect Method):**
    *   Reverted Attempt 2 changes.
    *   Added a patch for `dramatiq.brokers.stub.StubBroker.enqueue_message` alongside the `actor.send` patch.
    *   **Result:** Failed during test setup (`AttributeError: <class 'dramatiq.brokers.stub.StubBroker'> does not have the attribute 'enqueue_message'`).
6.  **Attempt 4: Patch `StubBroker.enqueue` (Correct Method):**
    *   Corrected the patch target from Attempt 3 to `dramatiq.brokers.stub.StubBroker.enqueue`.
    *   **Result:** Failed. Still got `Connection refused`. Patching the `StubBroker.enqueue` method didn't prevent the connection attempt.
7.  **Attempt 5: Explicit `StubBroker` setup at module level:**
    *   Removed the global `set_stub_broker` fixture from `conftest.py`.
    *   Added explicit `dramatiq.set_broker(StubBroker())` at the top level of `test_e2e_workflow.py`.
    *   Kept the patch on `actor.send` in `test_app_components`.
    *   **Result:** Failed. Still got `Connection refused`. Setting the broker at the module level wasn't early enough.
8.  **Attempt 6: Use `pytest_configure` hook:**
    *   Removed explicit setup from `test_e2e_workflow.py`.
    *   Added `pytest_configure` hook in `ops_core/tests/conftest.py` to set `StubBroker` globally before test collection.
    *   Kept the patch on `actor.send` in `test_app_components`.
    *   **Result:** Failed. Still got `Connection refused`. Even the earliest hook didn't seem to prevent the connection attempt reliably in the `tox` environment.

**Conclusion:**
The root cause of the `Connection refused` error remains elusive. Standard methods for ensuring `StubBroker` is used (global fixtures, module-level setup, `pytest_configure`) and various patching strategies (`actor.send`, actor object, `StubBroker.enqueue`) have not worked. The connection attempt seems deeply integrated into the `actor.send()` call path in a way that bypasses these mocks within the `tox` test environment.

**Next Steps (Post-Reset):**
Re-evaluate the interaction between Dramatiq, Pika, pytest fixtures, and the `tox` environment. Consider alternative testing strategies for the API -> Scheduler -> Broker interaction, potentially involving more targeted patching of Pika's connection methods directly, or exploring Dramatiq's testing utilities further.
