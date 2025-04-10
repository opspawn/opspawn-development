# Enhanced Testing & Debugging Strategy

## Purpose

Running the entire test suite via `tox -r` is essential for final verification but can be slow and obscure specific issues during development and debugging. This strategy provides a systematic workflow for efficiently testing changes and isolating failures using targeted test execution and structured logging.

## Core Workflow

1.  **Baseline Check (Full Run):**
    *   Always start by running the complete test suite to catch immediate, widespread issues.
    *   Command: `tox -e py312` (or the relevant environment)

2.  **Identify Failing Area(s):**
    *   If failures occur, analyze the `pytest` output to determine which high-level areas or batches are affected (e.g., `ops_core/tests/metadata`, `src/agentkit/tests/tools`, specific integration tests).

3.  **Run Failing Batch:**
    *   Execute only the tests within the identified failing batch/directory to confirm the failures in isolation. This uses `tox` to ensure environment consistency.
    *   Command: `tox -e py312 -- <path_to_batch_dir_or_file>`
    *   Example: `tox -e py312 -- ops_core/tests/metadata/`

4.  **Isolate Specific Failures (Granular Batching):**
    *   If multiple tests fail within a batch, or to focus on a specific failure, use `pytest`'s targeting options passed via `tox`:
        *   **By Keyword (`-k`):** Run tests whose names contain specific strings. Useful for related functions or features.
            *   Command: `tox -e py312 -- <path_to_batch_dir_or_file> -k "keyword1 or keyword2"`
            *   Example: `tox -e py312 -- ops_core/tests/metadata/test_sql_store.py -k "create or update"`
        *   **By Node ID:** Run a specific test function or class. Get the Node ID from the `pytest` failure summary.
            *   Command: `tox -e py312 -- <path_to_test_file>::<ClassName>::<test_function_name>`
            *   Example: `tox -e py312 -- ops_core/tests/metadata/test_sql_store.py::TestSQLStore::test_create_task`
        *   **By Marker (`-m`):** (Requires defining markers first in `pyproject.toml` or `pytest.ini`) Run tests with specific markers.
            *   Command: `tox -e py312 -- -m "marker_name"`
            *   Example: `tox -e py312 -- -m "database"`

5.  **Debug & Document:**
    *   **Create Debug Log:** Start a new debugging log file in `memory-bank/debugging/YYYY-MM-DD_brief_issue_description.md`.
    *   **Follow Log Structure:** Use a structure similar to `task_9.1_collection_error_summary.md`:
        *   **Date & Context:** Link to `TASK.md` item, describe the goal.
        *   **Initial Symptom:** Error message(s), command used.
        *   **Affected Batch/Area:** High-level location.
        *   **Isolation Command(s):** The `tox` command used for granular testing.
        *   **Debugging Log (Chronological):**
            *   *Timestamp/Step:* Action taken (e.g., "Added print statement", "Modified fixture X").
            *   *Command Used:* Specific command executed.
            *   *Observation/Result:* What happened? Error change? Output?
            *   *Hypothesis:* Why this step? What was expected?
        *   **Root Cause (if found):** Explanation.
        *   **Solution/Fix:** Code/config changes.
        *   **Verification Steps:** Commands run to confirm fix (isolated, batch, full).
        *   **Learnings/Takeaways:** Insights, documentation updates needed.
    *   **Iterate:** Use the isolated test command (`Step 4`) repeatedly as you apply fixes and record steps in the log.

6.  **Verify Fix:**
    *   **Isolated Test:** Confirm the fix works by running the specific, previously failing test(s) using the isolation command.
    *   **Batch Test:** Run the entire batch (`Step 3`) again to ensure no regressions were introduced within that area.
    *   **Full Test:** Run the full `tox` suite (`Step 1`) again to confirm overall integration and ensure no unexpected side effects elsewhere.

7.  **Update Memory Bank:**
    *   Update `activeContext.md` and `progress.md` with the status.
    *   If the debugging revealed new patterns, insights, or necessary changes to standard procedures, update this file (`testing_strategy.md`), `systemPatterns.md`, or `techContext.md` accordingly.

## Debugging Log Location

*   Store individual debugging logs in: `memory-bank/debugging/`

## Alternative: Direct `pytest` (Use with Caution)

Running `pytest` directly bypasses `tox`'s environment management. This can be faster for quick checks but requires manually setting the `PYTHONPATH` for the `src` layout and ensuring environment variables (like `DATABASE_URL`) are loaded, potentially via `dotenv`.

**Syntax:**

```bash
# Set PYTHONPATH, load .env (if needed), and run pytest
PYTHONPATH=src dotenv run -- python -m pytest <path_to_test_file_or_dir> [pytest_options]
```

**Caution:** Use this method carefully, as failures might be due to environment differences rather than code issues. Always confirm fixes using the `tox`-based workflow above.
