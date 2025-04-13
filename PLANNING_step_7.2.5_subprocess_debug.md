# PLANNING: Task 7.2 - Debug Dramatiq Worker Subprocess Invocation

## Objective
Diagnose and resolve the issue where the Dramatiq worker (`ops-core/src/ops_core/tasks/worker.py`) fails to consume messages when launched via `subprocess.Popen` from test scripts or fixtures, despite working correctly when launched directly via `tox exec`.

## Background
- Task 7.2 is blocked due to this issue.
- Manual execution via `tox exec` works.
- Execution via `subprocess.Popen` in `test_dramatiq_worker.py` and `ops-core/tests/conftest.py::live_dramatiq_worker` fails (worker starts but doesn't process messages).
- Dependency conflicts (e.g., with `locust`/`gevent`) were ruled out via a clean environment test (`PLANNING_step_7.2.4_clean_env_test.md`).
- The failure seems specific to the subprocess execution context.

## Debugging Plan

1.  **Environment & Context Comparison:**
    *   **Goal:** Identify discrepancies in the execution environment between the working (`tox exec`) and failing (`subprocess.Popen`) scenarios.
    *   **Actions:**
        *   Modify `ops-core/src/ops_core/tasks/worker.py` to log critical context information at startup *before* Dramatiq initialization (Full `os.environ`, `sys.executable`, `sys.path`, `os.getcwd()`, `os.getuid()`, `os.getgid()`).
        *   Enhance logging capture for the `subprocess.Popen` calls in `test_dramatiq_worker.py` and the `live_dramatiq_worker` fixture to reliably get the worker's stdout/stderr.
        *   Execute the worker via `tox exec ...` and capture its startup logs.
        *   Execute the worker via `test_dramatiq_worker.py` (and later, E2E tests) and capture its startup logs.
        *   Compare the captured context information from both methods.

2.  **`subprocess.Popen` Parameter Tuning:**
    *   **Goal:** Systematically adjust `subprocess.Popen` arguments to see if specific settings resolve the issue.
    *   **Actions:** In `test_dramatiq_worker.py` (and apply findings to `live_dramatiq_worker` fixture):
        *   Explicitly set `cwd`.
        *   Control environment inheritance (`env` parameter, testing minimal vs. inherited, ensuring critical vars are passed).
        *   Experiment with flags (`close_fds=True`, `start_new_session=True`).
        *   Verify `sys.executable` usage.
        *   Investigate different stdin/stdout/stderr handling (`subprocess.PIPE`, `subprocess.DEVNULL`, file redirection).

3.  **Enhanced Dramatiq/Pika Logging:**
    *   **Goal:** Obtain fine-grained logs from Dramatiq/Pika during connection/setup in the failing subprocess context.
    *   **Actions:**
        *   Configure Python's `logging` in `worker.py` to set `dramatiq` and `pika` loggers to `DEBUG`.
        *   Ensure debug logs are captured effectively when run via `subprocess.Popen`.
        *   Analyze logs for errors/warnings during broker connection, channel opening, queue declaration, or consumer setup.

4.  **Simplified Worker Test Case:**
    *   **Goal:** Determine if the failure is inherent to launching *any* Dramatiq worker via subprocess or specific to the `ops-core` worker's complexity.
    *   **Actions:**
        *   Create `minimal_worker.py` (bare essentials: broker, simple actor, worker startup).
        *   Create `test_minimal_worker.py` (launches `minimal_worker.py` via `subprocess.Popen`, sends message).
        *   If minimal setup works, incrementally add back `ops-core` worker elements to identify the failure point.

5.  **Asyncio Event Loop Investigation (If Necessary):**
    *   **Goal:** Explore potential conflicts between the parent test process's event loop (`pytest-asyncio`) and the child worker process's I/O loop.
    *   **Actions:** (Only if Steps 1-4 yield no clear cause)
        *   Review `pytest-asyncio` and Dramatiq/Pika event loop management.
        *   Theoretically consider `subprocess.Popen` interactions (though separate processes usually have independent loops).

## Visualization

```mermaid
graph TD
    A[Start Debugging Task 7.2] --> B{Worker Fails via subprocess.Popen};
    B --> C[Step 1: Environment Comparison];
    C --> D[Log Env Vars, sys.path, cwd, etc.];
    D --> E[Run via tox exec & subprocess];
    E --> F[Compare Logs for Discrepancies];
    B --> G[Step 2: Subprocess Tuning];
    G --> H[Modify Popen Params (cwd, env, fds, session, stdio)];
    H --> I[Test Impact on Worker Behavior];
    B --> J[Step 3: Detailed Logging];
    J --> K[Enable DEBUG Logs (Dramatiq, Pika)];
    K --> L[Capture & Analyze Subprocess Logs];
    B --> M[Step 4: Simplified Worker Test];
    M --> N[Create Minimal Worker/Actor];
    N --> O[Test Minimal Subprocess Launch];
    O --> P[Incrementally Add Complexity if Minimal Works];
    B --> Q[Step 5: Asyncio Investigation (If Needed)];
    Q --> R[Review Event Loop Management];
    R --> S[Check for Interference];
    F --> T{Identify Root Cause?};
    I --> T;
    L --> T;
    P --> T;
    S --> T;
    T -- Yes --> U[Formulate & Implement Fix];
    T -- No --> V[Re-evaluate/Consult];
    U --> W{Issue Resolved?};
    W -- Yes --> X[Complete Task 7.2];
    W -- No --> B;
    V --> X;
```

## Next Steps
Proceed with Step 1: Environment & Context Comparison.