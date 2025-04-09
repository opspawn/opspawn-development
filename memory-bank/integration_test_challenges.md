# Integration Testing Challenges: Async Agent Workflow (Task 3.5 Follow-up & Maint.8)

**Date:** 2025-04-08 (Updated)

## Goal (Original - Task 3.5 Follow-up)

The objective was to enhance the integration tests in `ops_core/tests/integration/test_async_workflow.py` to provide a more robust end-to-end validation of the asynchronous agent task execution flow:

`API (REST/gRPC) -> Scheduler -> Dramatiq Queue -> Worker -> execute_agent_task_actor -> Metadata Store Update`

This involved letting the actual `_run_agent_task_logic` function execute within the actor, while still mocking the `agentkit.Agent.run` method to control the agent's behavior without external dependencies (like LLMs).

## Core Challenge (Original - Task 3.5 Follow-up)

The primary difficulty lay in reliably triggering the execution of the `execute_agent_task_actor` within the pytest environment **while ensuring it uses the test-specific mocked dependencies** (specifically `InMemoryMetadataStore` and `OpsMcpClient` provided by fixtures) rather than the default instances obtained via the `get_metadata_store()` and `get_mcp_client()` dependency getters.

## Attempts and Issues Encountered (Original - Task 3.5 Follow-up)

Several approaches were attempted to simulate the worker processing the message queued by the API call:

1.  **`RabbitmqBroker` + Worker Thread (`worker.run`)**: Failed (`AttributeError: 'Worker' object has no attribute 'run'`).
2.  **`RabbitmqBroker` + Worker Thread (`worker.start`)**: Failed (`AssertionError: Task ... remained PENDING`). Worker likely didn't use mocked dependencies.
3.  **`RabbitmqBroker` + Direct Message Fetch/Process (`get_message`)**: Failed (`AttributeError: 'RabbitmqBroker' object has no attribute 'get_message'`).
4.  **`StubBroker` + Worker Simulation (`stub_broker.join`)**: Failed (`AssertionError: Task ... remained PENDING`). Actor likely didn't use patched dependencies. Follow-up using `worker.join()` also failed (`TypeError`, `AssertionError`).
5.  **`StubBroker` + Direct Message Fetch/Process (`worker.process_message`)**: Failed (`queue.Empty`). Message not reliably available after `send()`.
6.  **`StubBroker` + Manual Actor Execution**: Failed (`queue.Empty`). Message not reliably available after `send()`.

## Root Cause Hypothesis (Original - Task 3.5 Follow-up)

The consistent failure pattern pointed towards a fundamental issue with **dependency injection into the Dramatiq actor's execution context during testing** using `StubBroker.join` or `worker.process_message`. Patching dependency getters (`get_metadata_store`, `get_mcp_client`) within the test function's scope did not reliably affect the actor's execution context when invoked by Dramatiq's machinery.

## Current Solution & Limitations (Task 4.1.1 - 2025-04-06)

Given the challenges, the integration tests (`test_async_workflow.py`) were modified to patch the actor's `send` method, verifying the flow *up to* the message broker but not the actor's execution itself.

---

## Task Maint.8 Debugging (2025-04-08)

**Goal:** Resolve the original hanging issue observed when using `StubBroker.join()` with the async actor and mocked internal async calls (`Agent.run`, `ShortTermMemory.get_context`).

**Steps Taken & Observations:**

1.  **Simplify Actor Logic:** Commented out `await agent.run(...)` and `await agent.memory.get_context(...)` in `_run_agent_task_logic` within `ops_core/ops_core/scheduler/engine.py`, replacing them with `await asyncio.sleep(0.01)`.
2.  **Run Tests:** Executed `tox -e py312 -- pytest ops_core/tests/integration/test_async_workflow.py`.
3.  **Result:** The tests **did not hang**, confirming the original hang was related to the interaction between `StubBroker.join` and the mocked async calls (`AsyncMock`) within the actor. However, new errors emerged:
    *   **`AttributeError: 'InMemoryScheduler' object has no attribute '_metadata_store'`:** This error occurred during the setup of the `grpc_server` fixture (`test_grpc_api_async_agent_workflow_success`). Multiple attempts to fix this by correcting attribute access in the fixture code (`test_scheduler.metadata_store` vs `test_scheduler._metadata_store`) and adjusting how the `TaskServicer` was initialized within the fixture were unsuccessful, even when using `write_to_file`. The error trace consistently points to line 119, suggesting a persistent issue with the fixture setup or the state of the `test_scheduler` object being passed. Debug prints added to the fixture confirmed the `test_scheduler` object *should* have the `metadata_store` attribute.
    *   **`pika.exceptions.AMQPConnectionError` / `assert 500 == 201`:** These errors occurred in the REST API tests (`test_rest_api_async_agent_workflow_success`, `test_rest_api_async_agent_workflow_failure`). They indicate that when the API endpoint calls `scheduler.submit_task`, the subsequent call to `execute_agent_task_actor.send()` attempts to connect to a real RabbitMQ broker instead of using the `StubBroker`. Various patching strategies were attempted:
        *   Patching `actor.send` within the test function body (failed, patch applied too late).
        *   Patching `dramatiq.get_broker` globally within the test function (failed).
        *   Patching `actor.broker` directly using `mocker.patch.object` (failed).
        *   Patching `actor.send` within the `ops_core.scheduler.engine` namespace using `mocker.patch` (failed).

**Current Status (Maint.8):** Blocked. The original hanging issue is resolved by simplifying the actor, but replaced by persistent `AttributeError` in gRPC fixture setup and `AMQPConnectionError` in REST tests, indicating fundamental problems with patching/mocking the broker interaction and fixture setup within the `tox`/`pytest` environment.

## Next Steps (Potential - If Full Actor Execution is Required)

1.  **Revisit `grpc_server` Fixture:** Thoroughly investigate the `AttributeError`. Is the `test_scheduler` object somehow incorrect when passed? Is there a subtle interaction with `pytest-asyncio` or fixture scopes?
2.  **Revisit Broker Patching:** Why are the patches for the broker/send ineffective when triggered via the API call? Explore patching at different levels (e.g., patching the `InMemoryScheduler.submit_task` method itself, or patching `dramatiq.actor.Actor.send` globally).
3.  **Alternative Test Structure:** Consider structuring the test differently, perhaps by manually creating the message and calling the actor function directly within the test's async context, bypassing `StubBroker.join` entirely (though previous attempts at manual message fetching failed).
4.  **Dramatiq/pytest-asyncio Interaction:** Research known issues or recommended patterns for testing Dramatiq async actors specifically with `pytest-asyncio` and `StubBroker`.
