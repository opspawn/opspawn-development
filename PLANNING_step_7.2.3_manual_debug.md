# Debugging Plan: Task 7.2 - Manual Worker Invocation

**Date:** 2025-04-13

**Objective:** Continue debugging Task 7.2, specifically the issue where the Dramatiq worker receives messages from RabbitMQ but fails to invoke the corresponding actor code (`execute_agent_task_actor`). This manual debugging session aims to isolate the failure by running the API server and worker process independently and observing the worker logs upon task submission.

**Context:**
- Task 7.2 is blocked by this actor invocation failure.
- Previous debugging using `test_dramatiq_worker.py` and manual worker runs confirmed the issue persists outside the E2E test framework.
- The failure occurs *after* message receipt but *before* actor code entry.
- Several potential causes (env vars, middleware, actor code, Dramatiq version) were ruled out (see `memory-bank/debugging/2025-04-12_task7.2_worker_actor_invocation.md`).

**Steps:**

1.  **Environment Preparation:**
    *   Ensure Docker services (PostgreSQL, RabbitMQ) are running: `docker compose up -d` (from `1-t` directory).
    *   Identify command to activate the correct Python environment (e.g., `source .tox/py312/bin/activate` or prefix commands with `.tox/py312/bin/python`).
    *   Confirm API server command: `uvicorn ops_core.main:app --reload --host 0.0.0.0 --port 8000` (or similar).
    *   Confirm Worker command (high verbosity, `DRAMATIQ_TESTING` unset): `env DRAMATIQ_TESTING= dramatiq -v 2 ops_core.tasks.worker` (or similar, using the tox env python).

2.  **Manual Execution:**
    *   Open two separate terminals in `/home/sf2/Workspace/23-opspawn/1-t`.
    *   **Terminal 1:** Activate environment, start API server. Monitor logs.
    *   **Terminal 2:** Activate environment, start Dramatiq worker. Monitor logs for startup and actor discovery.
    *   Prepare task submission command (e.g., `curl` or adapted `send_test_message.py`):
        ```bash
        curl -X POST http://localhost:8000/api/v1/tasks/ -H "Content-Type: application/json" -d '{"task_type": "agent_task", "input_data": {"prompt": "Manual debug test prompt"}}'
        ```
    *   Execute the task submission command.

3.  **Observation & Analysis:**
    *   **Immediately** observe logs in Terminal 2 (Worker).
    *   Look for:
        *   Critical entry log: `!!!!!! ACTOR ENTRY POINT REACHED...`
        *   Dramatiq internal logs (processing, errors).
        *   Python tracebacks.
    *   Check RabbitMQ Management UI (http://localhost:15672) for message status (Ready/Unacked).

4.  **Diagnosis Scenarios:**
    *   **A: Actor log appears:** Contradicts previous findings. Investigate environment differences.
    *   **B: Error log appears:** Analyze error (Serialization? Dependency? Dramatiq internal?).
    *   **C: Silence:** Confirms previous findings. Requires deeper debugging (Dramatiq internals, library conflicts, simplify actor/payload further).

**Visualization:**

```mermaid
sequenceDiagram
    participant User as User/Debugger
    participant Terminal1 as Terminal 1 (API)
    participant Terminal2 as Terminal 2 (Worker)
    participant Curl as curl/Test Script
    participant API as Ops-Core API (uvicorn)
    participant Worker as Dramatiq Worker
    participant RabbitMQ
    participant PostgreSQL

    User->>Terminal1: Activate tox env
    User->>Terminal1: Start API (uvicorn ops_core.main:app)
    Terminal1->>API: Start Server
    API-->>Terminal1: Server Running

    User->>Terminal2: Activate tox env
    User->>Terminal2: Start Worker (env DRAMATIQ_TESTING= dramatiq -v 2 ops_core.tasks.worker)
    Terminal2->>Worker: Start Worker Process
    Worker->>RabbitMQ: Connect
    Worker-->>Terminal2: Worker Ready Logs (incl. Actor Discovery)

    User->>Curl: Prepare Task Submission Request
    User->>Curl: Execute curl command (POST /api/v1/tasks/)
    Curl->>API: HTTP POST Request
    API->>PostgreSQL: Create Task Record (Status: PENDING)
    API->>RabbitMQ: Send Task Message (execute_agent_task_actor)
    API-->>Curl: HTTP 202 Accepted (Task ID)
    Curl-->>User: Show Response

    Note over Worker, RabbitMQ: Worker detects message
    RabbitMQ->>Worker: Deliver Message

    alt Actor Invoked (Expected but unlikely based on prior logs)
        Worker->>Worker: Log "!!!!!! ACTOR ENTRY POINT REACHED..."
        Worker->>API/PostgreSQL: (Eventually) Update Task Status
        Worker->>RabbitMQ: Acknowledge Message
    else Actor NOT Invoked (Current Problem)
        Worker->>Terminal2: (Observe Logs - Any errors? Silence?)
        Note over Worker, RabbitMQ: Message remains Unacked in RabbitMQ?
        User->>Terminal2: Analyze Worker Logs
        User->>RabbitMQ: (Optional) Check Management UI
    end