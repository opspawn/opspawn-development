# Integration Testing Challenges: Async Agent Workflow (Task 3.5 Follow-up)

**Date:** 2025-04-06

## Goal

The objective was to enhance the integration tests in `ops_core/tests/integration/test_async_workflow.py` to provide a more robust end-to-end validation of the asynchronous agent task execution flow:

`API (REST/gRPC) -> Scheduler -> Dramatiq Queue -> Worker -> execute_agent_task_actor -> Metadata Store Update`

This involved letting the actual `_run_agent_task_logic` function execute within the actor, while still mocking the `agentkit.Agent.run` method to control the agent's behavior without external dependencies (like LLMs).

## Core Challenge

The primary difficulty lies in reliably triggering the execution of the `execute_agent_task_actor` within the pytest environment **while ensuring it uses the test-specific mocked dependencies** (specifically `InMemoryMetadataStore` and `OpsMcpClient` provided by fixtures) rather than the default instances obtained via the `get_metadata_store()` and `get_mcp_client()` dependency getters.

## Attempts and Issues Encountered

Several approaches were attempted to simulate the worker processing the message queued by the API call:

1.  **`RabbitmqBroker` + Worker Thread (`worker.run`)**:
    *   **Attempt:** Use the real `RabbitmqBroker`, start a `dramatiq.Worker` in a background `threading.Thread` targeting `worker.run`, and poll the metadata store.
    *   **Issue:** Failed with `AttributeError: 'Worker' object has no attribute 'run'`. The `run` method is not the correct entry point for the thread target.

2.  **`RabbitmqBroker` + Worker Thread (`worker.start`)**:
    *   **Attempt:** Use the real `RabbitmqBroker`, start a `dramatiq.Worker` in a background `threading.Thread` targeting `worker.start`, and poll the metadata store.
    *   **Issue:** Tests failed with `AssertionError: Task ... remained PENDING after timeout.`. This indicated the worker thread wasn't processing the message and updating the store, likely due to issues with dependency injection across threads (the actor probably got the default store, not the test's mocked store).

3.  **`RabbitmqBroker` + Direct Message Fetch/Process (`get_message`)**:
    *   **Attempt:** Use the real `RabbitmqBroker`, fetch the message directly using `broker.get_message()`, instantiate a `Worker`, and call `worker.process_message(message)`.
    *   **Issue:** Failed with `AttributeError: 'RabbitmqBroker' object has no attribute 'get_message'`. This method is not available on the `RabbitmqBroker`. Also encountered issues with finding the correct `QueueEmpty` exception.

4.  **`StubBroker` + Worker Simulation (`stub_broker.join`)**:
    *   **Attempt:** Revert to `StubBroker`, patch dependency getters (`get_metadata_store`, `get_mcp_client`) using `mocker`, submit the task, and use `stub_broker.join(queue_name)` to process the message.
    *   **Issue:** Initially failed with `dramatiq.errors.QueueNotFound` even after explicitly declaring the queue. After fixing that, tests still failed with `AssertionError: Task ... remained PENDING after timeout.`. This strongly suggests the actor executed via `stub_broker.join` did *not* receive the patched dependencies.
    *   **Follow-up (2025-04-06):** Attempted using `worker.join()` instead of `stub_broker.join()`. Failed with `TypeError: Worker.join() got an unexpected keyword argument 'timeout'`. Removing the timeout argument still resulted in the actor's mocked logic (`_run_agent_task_logic`) not being called (`AssertionError: Expected ... to have been called once. Called 0 times.`).

5.  **`StubBroker` + Direct Message Fetch/Process (`worker.process_message`)**:
    *   **Attempt (2025-04-06):** Use `StubBroker`, patch dependency getters at source (`ops_core.dependencies`), fetch message using `stub_broker.queues[queue_name].get(timeout=...)`, instantiate `Worker`, call `worker.process_message(message)`.
    *   **Issue:** Failed with `queue.Empty` exception, indicating the message wasn't retrieved from the `StubBroker` queue within the timeout, even immediately after the API call that should have enqueued it. This suggests potential timing issues or incorrect assumptions about how `StubBroker` handles message availability synchronously after `send()`.

6.  **`StubBroker` + Manual Actor Execution**:
    *   **Attempt (2025-04-06):** Use `StubBroker`, patch dependency getters at source (`ops_core.dependencies`), patch `Agent` class, fetch message using `queue.get()`, decode message, manually `await execute_agent_task_actor()` with decoded arguments.
    *   **Issue:** Failed with `queue.Empty` exception, same as attempt #5. The message is not reliably available in the `StubBroker` queue immediately after the `send()` call within the test's execution flow.

## Root Cause Hypothesis

The consistent failure pattern (tasks remaining PENDING) across different broker/worker simulation approaches points towards a fundamental issue with **dependency injection into the Dramatiq actor's execution context during testing**.

-   The FastAPI/gRPC endpoints correctly use overridden dependencies (`test_metadata_store`, `mock_mcp_client`) via `app.dependency_overrides`.
-   However, when the `execute_agent_task_actor` runs (either via a real worker thread or `StubBroker.join`/`worker.process_message`), it calls the original `get_metadata_store` and `get_mcp_client` functions within `ops_core.scheduler.engine`.
-   Patching dependency getters (`get_metadata_store`, `get_mcp_client`) using `mocker.patch` within the test function's scope **does not reliably affect** the execution context of the actor when invoked by Dramatiq's `StubBroker` machinery (`worker.join()` or `stub_broker.join()`). The actor appears to import/use the original, unpatched getters.
-   Patching the getters at their source module (`ops_core.dependencies`) **does appear to work** for dependency injection when the actor is eventually called.
-   However, simulating the actor's execution using `StubBroker`'s `worker.join()` or `stub_broker.join()` **does not reliably trigger** the `await` on the actor's internal async logic (specifically, `_run_agent_task_logic` when patched with `AsyncMock`), leading to assertion failures (`assert_awaited_once`).
-   Manually fetching the message from `StubBroker.queues[queue_name]` using `queue.get()` **fails with `queue.Empty`**, even with a short timeout, suggesting the message isn't immediately available for synchronous retrieval after the `actor.send()` call within the test's async flow.

## Current Solution & Limitations (Task 4.1.1 - 2025-04-06)

Given the challenges with simulating the actor's execution reliably via `StubBroker` in the `pytest-asyncio` environment, the integration tests (`test_async_workflow.py`) were modified to:
1.  Patch the actor's `send` method (`ops_core.scheduler.engine.execute_agent_task_actor.send`).
2.  Verify that the API call correctly triggers the scheduler to call `actor.send` with the expected arguments (`task_id`, `input_data`).
3.  Assert that the task remains in the `PENDING` state in the metadata store (as the actor execution is mocked away at the `send` level).

**Limitation:** This approach verifies the flow *up to* the message broker but **does not** verify the actor's execution itself or its interaction with the (patched) dependencies within the integration test context. Coverage for the actor's internal logic relies solely on the unit tests in `test_engine.py`.

## Next Steps (Potential - If Full Actor Execution is Required)

If verifying the actor's execution with patched dependencies within the integration test is strictly necessary, further investigation is needed:
1.  **Dramatiq Testing Utilities:** Deep dive into Dramatiq's official testing documentation or examples specifically for testing `async` actors with `StubBroker` and `pytest-asyncio` to find the recommended pattern. There might be specific configurations or helper methods needed.
2.  **Event Loop Synchronization:** Investigate if manual event loop steps (`loop.run_until_complete` or similar, if applicable with `pytest-asyncio`) are needed after `actor.send()` before the message becomes available in the `StubBroker` queue for manual fetching.
3.  **Refactor Dependency Acquisition (Revisit):** Reconsider passing serialized identifiers or configurations in the message, allowing the actor to look up test-specific dependencies from a shared (but carefully managed) test context. This adds complexity.
4.  **Alternative Testing Broker:** Explore if other testing brokers or strategies exist that integrate more smoothly with `asyncio` testing.
