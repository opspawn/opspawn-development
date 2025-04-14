# Plan: Resume Task 7.2 Debugging - Test Fresh Session Fix

**Date:** 2025-04-13

**Objective:** Resume debugging Task 7.2 (Execute & Debug Live E2E Tests) by testing the "fresh session" approach to resolve the database status visibility issue in the `get_task` API endpoint.

**Steps:**

1.  **Re-apply "Fresh Session" Code Change:**
    *   **File:** `ops-core/src/ops_core/api/v1/endpoints/tasks.py`
    *   **Function:** `get_task(task_id: UUID)`
    *   **Modification:** Modify the function to create a new, independent `AsyncSession` for this specific read operation using the `async_session_factory` instead of using FastAPI's dependency-injected session (`Depends(get_db_session)`). Ensure the read operation (`session.get(Task, task_id)`) occurs within an `async with` block managing the new session.
    *   **Verification:** Confirm correct import of `async_session_factory`, usage of `async with`, removal of `Depends(get_db_session)` parameter.

2.  **Execute the Target E2E Test:**
    *   Run the specific test command:
        ```bash
        tox exec -e py -- pytest ops-core/tests/integration/test_live_e2e.py::test_submit_task_and_poll_completion -m live -vvv -s
        ```
    *   Ensure the environment has necessary configurations (e.g., `OPENAI_API_KEY`, running Docker services).

3.  **Analyze Test Results:**
    *   **Scenario A (Pass):** Indicates the "fresh session" approach likely resolved the DB visibility issue.
    *   **Scenario B (Fail - Timeout/Stale Status):** Indicates the approach was ineffective; suspect a deeper issue.
    *   **Scenario C (Fail - New Error):** Analyze the new error traceback.

**Visual Representation:**

```mermaid
graph TD
    A[Start: Resume Task 7.2 Debugging] --> B{Step 1: Re-apply Fresh Session Code};
    B --> C[Step 2: Run E2E Test Command];
    C --> D{Step 3: Analyze Test Result};
    D -- Test Passes --> E[Conclusion: DB Visibility Likely Fixed!];
    D -- Test Fails (Timeout/Stale Status) --> F[Conclusion: Fresh Session Ineffective. Deeper Issue Suspected.];
    D -- Test Fails (New Error) --> G[Conclusion: New Issue Encountered. Analyze Error.];