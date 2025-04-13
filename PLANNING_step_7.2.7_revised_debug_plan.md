# PLANNING: Task 7.2 - Revised Debugging Plan (2025-04-13)

## Objective

Diagnose and resolve the root cause of the Dramatiq worker failing to consume messages and invoke the target actor (`execute_agent_task_actor` or `simple_task` in minimal case) when launched via the `dramatiq` CLI within the project's `tox` environment.

## Background

Previous debugging steps isolated the failure to the worker process itself when run via the CLI, regardless of whether launched by `subprocess.Popen`, `tox exec`, or direct python execution within the `.tox/py312` environment. The worker connects to RabbitMQ and registers as a consumer, but fails to process messages. Analysis of a `python -m trace` log proved difficult. A strong hypothesis points towards dependency conflicts or environment issues within the `tox` environment interfering with Dramatiq/Pika's event loop or message dispatch.

## Revised Plan

This plan prioritizes alternative isolation techniques over further trace log analysis.

### Step 1: Clean Virtual Environment Test (Optional but Recommended)

*   **Goal:** Directly test the hypothesis that dependency conflicts within the `.tox/py312` environment are the root cause.
*   **Action:**
    1.  Create a fresh virtual environment completely outside the project's `tox` structure (e.g., `/tmp/dramatiq_test_venv`).
    2.  Install only the absolute minimum required dependencies into this venv:
        *   `python -m pip install dramatiq[rabbitmq]`
        *   (Potentially `pydantic` if needed by the minimal actor, TBD)
    3.  Copy `minimal_worker.py` and `send_test_message.py` into a temporary directory accessible by the venv.
    4.  Ensure RabbitMQ is running (via `docker compose up -d rabbitmq`).
    5.  Activate the clean venv.
    6.  Start the worker from the clean venv using the `dramatiq` CLI: `python -m dramatiq minimal_worker:broker minimal_worker --verbose`
    7.  Send a test message using `send_test_message.py` (can be run from the project's `tox` env or the clean venv after installing necessary DB deps if the script requires them).
*   **Expected Outcome:**
    *   **If Worker Processes Message:** Confirms the issue lies within the project's `tox` environment dependencies. Further investigation would focus on identifying the conflicting package(s) (e.g., `locust`/`gevent`).
    *   **If Worker Still Fails:** Suggests the issue is more fundamental to Dramatiq/Pika interaction or the worker code itself, even in a minimal environment. Proceed to Step 2.

### Step 2: Programmatic Worker Startup (Primary Next Step)

*   **Goal:** Isolate the core worker/actor/broker interaction from the `dramatiq` CLI's environment setup, argument parsing, and process management.
*   **Action:**
    1.  Create a new script: `start_worker_programmatically.py`.
    2.  In this script:
        *   Import necessary components: `RabbitmqBroker`, `Worker`, the actor function (`simple_task` from `minimal_worker` or `execute_agent_task_actor` from `engine.py`), middleware (like `AsyncIO`).
        *   Instantiate the `RabbitmqBroker`.
        *   Add required middleware to the broker.
        *   Declare the actor(s) on the broker instance.
        *   Instantiate a `Worker` instance, passing the broker and desired concurrency settings (e.g., `worker_threads=1`).
        *   Call the `worker.run()` method to start the worker loop.
    3.  Run this script from within the standard `tox` environment: `tox exec -e py312 -- python start_worker_programmatically.py`
    4.  While the programmatic worker is running, send a test message using `send_test_message.py`.
*   **Expected Outcome:**
    *   **If Worker Processes Message:** Confirms the issue is specific to the `dramatiq` CLI execution path (loading, argument handling, signal handling, etc.). This would likely unblock Task 7.2, as the E2E tests could potentially be modified to start the worker programmatically.
    *   **If Worker Still Fails:** Indicates a deeper issue within Dramatiq/Pika or the actor/broker interaction itself, even when bypassing the CLI. Proceed to Step 3.

### Step 3: Contingency - Deeper Debugging

*   **Goal:** Further diagnose the failure if both the clean environment and programmatic startup fail.
*   **Potential Actions (Choose based on previous findings):**
    *   **Basic Pika Consumer:** Write and run a simple, standalone Pika consumer script within the `.tox/py312` environment to confirm basic message consumption works outside of Dramatiq.
    *   **Monkey-Patching/Library Logging:** Add detailed logging/print statements directly into the installed Dramatiq or Pika library code within `.tox/py312/lib/python3.12/site-packages/` to trace internal execution flow during message handling.
    *   **RabbitMQ Server Tracing:** Enable and analyze message tracing on the RabbitMQ server itself to see exactly what happens to the message after the `Basic.ConsumeOk`.

## Documentation

*   Progress and findings for these steps will be logged in a new file: `memory-bank/debugging/YYYY-MM-DD_task7.2_revised_debug.md`.
*   This plan supersedes `PLANNING_step_7.2.6_cli_debug.md`.