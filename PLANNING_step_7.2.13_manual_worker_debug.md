# Debugging Plan: Task 7.2 - Manual Worker for `test_submit_task_and_expect_failure`

**Date:** 2025-04-13

**Objective:** Resume debugging Task 7.2, specifically the `test_submit_task_and_expect_failure` test case, using a manually launched worker process to bypass the fixture subprocess issue. Analyze the test logic and worker output to understand why the task doesn't reach the expected `FAILED` state.

**Context:**
*   The `live_dramatiq_worker` fixture in `ops-core/tests/conftest.py` is known to fail when launching its worker subprocess within the pytest environment.
*   The fixture code has already been modified (lines 432-441) to *bypass* the subprocess launch attempt, assuming a manual worker will be used.
*   A manual worker launch command (`dotenv run -- .tox/py/bin/python -m dramatiq ops_core.tasks.worker --verbose`) has been previously confirmed to work.

**Plan:**

1.  **Manual Worker Launch:** The user will open a new terminal, navigate to the project root (`/home/sf2/Workspace/23-opspawn/1-t`), and execute the following command to start the worker manually:
    ```bash
    dotenv run -- .tox/py/bin/python -m dramatiq ops_core.tasks.worker --verbose
    ```
    This terminal should remain open to monitor worker output. *(Status: User confirmed worker started successfully)*

2.  **Execute Specific Test:** Once the manual worker is running, the user will execute the specific failing test in a separate terminal (also from the project root):
    ```bash
    pytest ops-core/tests/integration/test_live_e2e.py::test_submit_task_and_expect_failure -m live -s -v
    ```

3.  **Analysis:** After the test run completes, analyze the output from both the `pytest` command and the manual worker terminal to diagnose why the task does not reach the expected `FAILED` state.

4.  **Switch Mode:** Once the analysis is complete and the root cause is understood, request switching to Debug mode to implement the necessary fixes.