# Plan: Investigate Direct Worker Execution (Task 7.2 Debugging)

**Date:** 2025-04-13

**Objective:** Resume Task 7.2 debugging by investigating if the `tox exec` wrapper interferes with Dramatiq worker message processing. Previous debugging steps strongly suggest the issue might be related to how the worker is launched via `tox exec -- dramatiq ...`, rather than the core actor code itself.

**Plan:**

1.  **Goal:** Determine if the Dramatiq worker (`ops_core.tasks.worker`) can successfully process messages when run directly within the activated `tox` environment, bypassing the `tox exec` wrapper.
2.  **Prerequisites:**
    *   Ensure no other instances of the `ops_core` Dramatiq worker are running to avoid interference.
    *   Ensure required services (RabbitMQ, potentially PostgreSQL DB) are running (likely already up from previous E2E test attempts).
3.  **Steps:**

    *   **Step 1: Terminate Existing Workers (Safety Check):**
        *   *Action:* Check for and terminate any lingering `dramatiq ops_core.tasks.worker` processes.
        *   *Rationale:* Prevents interference from potentially zombie processes from previous runs. We can use `pgrep` first to check, then `pkill` if necessary.
    *   **Step 2: Activate `tox` Environment:**
        *   *Action:* Activate the `tox` virtual environment for `ops-core`.
        *   *Command:* `source ops-core/.tox/py/bin/activate`
        *   *Rationale:* Ensures the worker runs with the correct dependencies and Python interpreter defined in `tox.ini`.
    *   **Step 3: Run Worker Directly:**
        *   *Action:* Start the Dramatiq worker using the Python interpreter from the activated environment, running it in the background and logging output.
        *   *Command:* `python -m dramatiq ops_core.tasks.worker --verbose > worker_direct_run.log 2>&1 &`
        *   *Rationale:* Runs the worker directly, bypassing `tox exec`. `--verbose` provides more detailed logs. Output is redirected to `worker_direct_run.log` for analysis. Running in the background (`&`) allows the next step.
    *   **Step 4: Send Test Message:**
        *   *Action:* Use the existing test script to send a message to the queue. Using `tox exec` for the *sender* is acceptable here, as the hypothesis focuses on the *worker's* execution environment.
        *   *Command:* `tox exec -e py -- python send_test_message_clean_env.py`
        *   *Rationale:* Triggers the worker to process a message.
    *   **Step 5: Observe Worker Output:**
        *   *Action:* Examine the log file `worker_direct_run.log`.
        *   *Rationale:* Check for the "ACTOR ENTRY POINT REACHED" log message (or similar confirmation) and any errors to determine if the message was processed successfully.
4.  **Expected Outcome & Interpretation:**
    *   **Success:** If `worker_direct_run.log` shows the actor processing the message, it strongly indicates that `tox exec` (or the way it wraps the `dramatiq` command) is the source of the interference.
    *   **Failure:** If the worker still fails to process the message even when run directly in the activated environment, the problem likely lies deeper within the environment setup provided by `tox` itself, potential initialization race conditions, or subtle code interactions not previously triggered.

**Visual Plan:**

```mermaid
sequenceDiagram
    participant Roo as Roo (Planner)
    participant User as User (Executor)
    participant Terminal as Terminal
    participant ToxEnv as Activated Tox Env
    participant Worker as Worker Process
    participant Sender as send_test_message.py
    participant LogFile as worker_direct_run.log
    participant RabbitMQ as RabbitMQ

    Roo->>User: Present Plan
    User->>Roo: Approve Plan
    User->>Terminal: pgrep/pkill worker (Optional Check)
    User->>Terminal: source ops-core/.tox/py/bin/activate
    Terminal-->>User: Environment Activated
    User->>Terminal: python -m dramatiq ... &> worker_direct_run.log &
    Terminal->>ToxEnv: Start Worker Process
    ToxEnv->>Worker: Initialize & Connect to RabbitMQ
    Worker-->>LogFile: Log Startup Info
    User->>Terminal: tox exec -- python send_test_message.py
    Terminal->>Sender: Execute Script
    Sender->>RabbitMQ: Send Message
    Worker->>RabbitMQ: Consume Message
    alt Message Processed Successfully
        Worker->>LogFile: Log "ACTOR ENTRY POINT REACHED"
    else Message Processing Fails
        Worker->>LogFile: Log Errors or Silence (No Actor Log)
    end
    User->>Terminal: cat worker_direct_run.log (or read file)
    Terminal-->>User: Show Log Contents
    User->>Roo: Report Outcome