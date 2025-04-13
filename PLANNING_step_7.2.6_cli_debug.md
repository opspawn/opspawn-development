# Plan: Debugging Dramatiq CLI Worker Invocation (Task 7.2 Continuation)

**Goal:** Identify the root cause of the `dramatiq` CLI failing to correctly initialize and run the `minimal_worker.py` actor, which prevents message consumption within the `tox` environment.

**Phase 1: Deep Environment &amp; Process Comparison**

1.  **Objective:** Pinpoint subtle differences between a working Python script invocation (directly calling the actor logic) and the failing `dramatiq` CLI invocation within the same `tox` environment.
2.  **Steps:**
    *   **1.1 Create a "Working Invocation" Script:** Develop a new Python script (`run_minimal_actor_directly.py`). This script will:
        *   Import the target actor function (`minimal_worker.simple_task`).
        *   Manually establish a Dramatiq broker connection using settings identical to `minimal_worker.py`.
        *   Attempt to directly invoke the actor's underlying function (`minimal_worker.simple_task.fn(...)`) with sample data.
        *   Log critical environment details at startup (environment variables, `sys.path`, `sys.modules` list *before* broker setup, Current Working Directory, User/Group ID).
    *   **1.2 Execute Both Scenarios &amp; Capture Detailed Logs:**
        *   Run the working script within the tox environment: `tox exec -e py312 -- python run_minimal_actor_directly.py`
        *   Run the failing CLI invocation with verbose logging: `tox exec -e py312 -- python -m dramatiq minimal_worker --verbose` (ensure `minimal_worker.py` is also configured to log its environment details).
        *   Carefully capture and save the complete stdout and stderr streams for both executions.
    *   **1.3 Meticulously Compare Logs:** Perform a detailed comparison of the captured logs, focusing on:
        *   Environment variables (especially `PYTHONPATH`, `DRAMATIQ_*`, `PATH`).
        *   Contents of `sys.path`.
        *   List of loaded modules (`sys.modules`) before significant Dramatiq/broker activity.
        *   CWD, UID/GID.
        *   Any subtle differences in library versions or paths being used.

**Phase 2: Dramatiq CLI Internals Investigation**

1.  **Objective:** Understand the precise sequence of actions the `dramatiq` CLI takes to load the worker module, discover actors, and start the processing loop.
2.  **Steps:**
    *   **2.1 Code Review (Optional but Recommended):** Briefly examine the source code for the `dramatiq` command-line entry point. Focus on how it parses arguments, imports the specified module(s), finds actors, and initializes the `Worker` instance(s).
    *   **2.2 Trace Execution:** Utilize Python's built-in tracing capabilities (`trace` module or `pdb`) to observe the execution flow of the `dramatiq` CLI when it attempts to load `minimal_worker.py`.
        *   Example command: `tox exec -e py312 -- python -m trace --trace -m dramatiq minimal_worker --verbose`
        *   Pay close attention to the module import sequence, broker setup calls, actor discovery logic, and the point where the `Worker.run()` loop is initiated. Look for any unexpected deviations, errors, or silent exits.

**Phase 3: Alternative Worker Startup Method (If Phases 1 &amp; 2 are Inconclusive)**

1.  **Objective:** Determine if programmatically initializing and running the Dramatiq worker loop from a Python script bypasses the issue encountered with the CLI tool.
2.  **Steps:**
    *   **3.1 Create Programmatic Startup Script:** Develop a script (`start_worker_programmatically.py`) that:
        *   Imports necessary Dramatiq classes (`Worker`, `RabbitmqBroker`).
        *   Imports the target actor (`minimal_worker.simple_task`).
        *   Explicitly instantiates the `RabbitmqBroker`.
        *   Explicitly instantiates the `Worker`, passing the broker and a list containing the imported actor.
        *   Calls the `worker.run()` method to start the processing loop.
    *   **3.2 Test Programmatic Startup:** Execute this new script via `tox exec` (`tox exec -e py312 -- python start_worker_programmatically.py`) and use `send_test_message.py` to check if messages are processed.
    *   **3.3 Analyze Results:** If this method succeeds, it strongly implicates the `dramatiq` CLI's specific initialization process as the source of the problem. This could offer a viable workaround for the E2E tests, although understanding the CLI's failure mechanism remains the primary goal.

**Contingency:**

*   If the root cause remains elusive after these phases, the next step would involve more invasive debugging, potentially by adding fine-grained logging directly into the installed `dramatiq` and `pika` library code within the `.tox/py312/lib/python3.12/site-packages/` directory to trace internal operations during broker connection, channel setup, and message consumption attempts.

**Documentation:**

*   All findings, observations, and conclusions from these steps should be meticulously documented, continuing the log in `memory-bank/debugging/2025-04-13_task7.2_subprocess_investigation.md` or starting a new dated file for this session.

**Plan Visualization:**

```mermaid
graph TD
    A[Start Debugging Task 7.2] --> B{Current State: CLI Invocation Fails};
    B --> C[Phase 1: Environment Comparison];
    C --> C1[Create 'Working' Script (Direct Actor Call)];
    C --> C2[Run 'Working' Script &amp; Failing CLI];
    C --> C3[Capture &amp; Compare Logs (Env, sys.path, sys.modules)];
    C3 --> D{Subtle Difference Found?};
    D -- Yes --> E[Analyze Difference -> Hypothesize Cause];
    D -- No --> F[Phase 2: CLI Internals Investigation];
    F --> F1[Review Dramatiq CLI Code (Optional)];
    F --> F2[Trace CLI Execution (trace/pdb)];
    F2 --> G{CLI Loading/Init Issue Identified?};
    G -- Yes --> H[Analyze CLI Issue -> Hypothesize Cause];
    G -- No --> I[Phase 3: Programmatic Worker Startup];
    I --> I1[Create Programmatic Startup Script];
    I --> I2[Test Programmatic Script];
    I2 --> J{Programmatic Startup Works?};
    J -- Yes --> K[Confirms CLI Issue / Potential Workaround];
    J -- No --> L[Consider Deep Library Logging / Re-evaluate];
    E --> M[Test Hypothesis];
    H --> M;
    K --> M[Test Hypothesis / Use Workaround];
    L --> P[Re-evaluate Strategy];
    M --> N{Issue Resolved?};
    N -- Yes --> O[Unblock Task 7.2];
    N -- No --> P;

    subgraph Legend
        direction TB
        L1[Phase/Step]
        L2{Decision Point}
        L3[Outcome/Action]
    end

    style Legend fill:#eee,stroke:#333,stroke-width:1px
```

---