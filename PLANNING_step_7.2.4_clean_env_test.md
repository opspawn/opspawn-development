# Plan: Test Dramatiq Worker in Clean Environment (Task 7.2 Debugging)

**Objective:** Test the hypothesis that a dependency conflict within the `.tox/py312` environment (potentially `locust`/`gevent`) is preventing the Dramatiq worker from consuming messages. This will be done by running the worker in a clean, minimal virtual environment.

**Date:** 2025-04-13

## Steps

1.  **Prerequisites:**
    *   Ensure required services (RabbitMQ, PostgreSQL) are running.
        *   Command (from `/home/sf2/Workspace/23-opspawn/1-t`): `docker compose up -d`
    *   Confirm necessary environment variables (`DATABASE_URL`, `RABBITMQ_URL`, etc.) are accessible, likely via `.env` in the workspace root.

2.  **Create Clean Virtual Environment:**
    *   Create a temporary virtual environment outside the project structure.
    *   Command: `python3 -m venv /tmp/dramatiq_test_env`

3.  **Install Minimal Dependencies:**
    *   Activate the new environment.
        *   Command: `source /tmp/dramatiq_test_env/bin/activate`
    *   Install only essential runtime dependencies, excluding development/testing extras. Install local submodules editable.
    *   Commands (run from `/home/sf2/Workspace/23-opspawn/1-t` *after activating venv*):
        ```bash
        pip install wheel # Ensure wheel is present
        pip install python-dotenv SQLAlchemy asyncpg psycopg2-binary alembic "dramatiq[rabbitmq]"
        pip install -e ./agentkit # Install agentkit editable
        pip install -e ./ops-core # Install ops-core editable
        ```
    *   Verify `locust` and `gevent` are *not* installed.
        *   Command: `pip list | grep -E 'locust|gevent'` (Expect no output)

4.  **Run the Worker:**
    *   Execute the Dramatiq worker using the clean environment's Python interpreter.
    *   Set `PYTHONPATH` explicitly for `src` layouts.
    *   Command (run from `/home/sf2/Workspace/23-opspawn/1-t` *while clean venv is active*):
        ```bash
        PYTHONPATH=/home/sf2/Workspace/23-opspawn/1-t/ops-core/src:/home/sf2/Workspace/23-opspawn/1-t/agentkit/src \
        dotenv run -- \
        /tmp/dramatiq_test_env/bin/python -m dramatiq --watch /home/sf2/Workspace/23-opspawn/1-t/ops-core/src ops_core.tasks.broker:broker ops_core.tasks.worker -vv
        ```
        *(Note: Assumes `.env` is configured. `-vv` for max verbosity.)*

5.  **Send a Test Message:**
    *   In a *separate terminal*, use a suitable script (`test_dramatiq_worker.py` or `send_test_message.py`) to dispatch a task message.
    *   This script should likely be run from the *original* `.tox/py312` environment or another configured environment.
    *   Example command (using `test_dramatiq_worker.py` from `tox` env):
        ```bash
        # In new terminal, cd /home/sf2/Workspace/23-opspawn/1-t
        tox -e py312 -- python test_dramatiq_worker.py
        ```

6.  **Observe and Analyze:**
    *   Monitor the worker terminal (Step 4) for message consumption logs and successful actor execution. Check for errors.
    *   Check RabbitMQ Management UI (if accessible) for message status.
    *   **Analysis:**
        *   **Success:** Supports the dependency conflict hypothesis (likely `locust`/`gevent`).
        *   **Failure:** Root cause is elsewhere (Dramatiq/Pika interaction, env vars, path issues).

---

## Execution Results (2025-04-13 Session)

1.  **Prerequisites:** Docker services started successfully.
2.  **Create Venv:** `/tmp/dramatiq_test_env` created successfully.
3.  **Install Dependencies:**
    *   Initial minimal dependencies installed.
    *   Attempting to start worker failed due to missing `chromadb` dependency (imported by `ops_core.scheduler.engine`).
    *   Installed `chromadb`. This introduced dependency conflicts (`protobuf`, `grpcio`) with `ops-core`.
    *   Reinstalled correct `protobuf` and `grpcio` versions required by `ops-core`.
    *   Temporarily commented out `ChromaLongTermMemory` import and usage in `ops_core.scheduler.engine` to avoid the dependency conflict for this specific test.
4.  **Run Worker:** Worker started successfully in the clean environment (`/tmp/dramatiq_test_env`) after commenting out LTM code.
5.  **Send Message:** `test_dramatiq_worker.py` was executed using `tox exec -e py312 -- python test_dramatiq_worker.py`. The script sent the message successfully but timed out waiting for completion, as the worker subprocess it started internally failed (as expected).
6.  **Observe & Analyze:**
    *   The manually started worker running in the clean environment (`/tmp/dramatiq_test_env`) **did not** show any logs indicating it received or processed the message sent by the test script. It remained idle after startup.
    *   Subsequent attempts to modify `test_dramatiq_worker.py` (simplifying worker args, changing launch order) also failed; the worker subprocess started by the script never processed the message.

## Conclusion

*   The clean environment test **invalidated** the hypothesis that a dependency conflict (e.g., `locust`/`gevent`) within the `.tox/py312` environment was the cause of the worker failure.
*   The failure seems specific to launching the Dramatiq worker as a **subprocess** using `subprocess.Popen` from within the test script (`test_dramatiq_worker.py`) or test fixtures (`ops-core/tests/conftest.py`), regardless of environment cleanliness or launch order variations attempted so far.
*   Direct execution via `tox exec` (after fixing actor code bugs in a previous session) *does* work, highlighting the difference in behavior when run as a subprocess.
*   The root cause likely lies in subtle interactions related to subprocess management, environment variable inheritance (despite attempts to control it), `PYTHONPATH` handling in subprocesses, or potentially Dramatiq/Pika/asyncio behavior when run under `subprocess.Popen`.

## Next Steps (Internal to Session)

*   Reverted temporary code changes disabling LTM in `ops_core.scheduler.engine`.
*   Stopped the manually started clean worker process.
*   Prepared to update documentation and Git state before ending the session.