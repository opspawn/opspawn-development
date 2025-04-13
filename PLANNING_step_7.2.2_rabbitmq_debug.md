# Planning: Task 7.2 - Step 2: RabbitMQ Debugging

**Date:** 2025-04-12

**Objective:** Diagnose why the Dramatiq worker (`execute_agent_task_actor`) is not being invoked when messages are sent via the `test_dramatiq_worker.py` script by observing RabbitMQ state.

**Context:**
- Task 7.2 is focused on debugging live E2E test failures.
- An isolation script (`test_dramatiq_worker.py`) is being used to test the worker independently.
- Logs confirm the worker starts, connects to RabbitMQ, and discovers the actor.
- The RabbitMQ management UI port (15672) has been exposed.
- The immediate issue is that the actor function doesn't seem to run when a message is sent.

**Plan:**

1.  **Verify RabbitMQ UI Access:**
    *   Confirm accessibility of the RabbitMQ management interface at http://localhost:15672.
    *   Log in using credentials `guest`/`guest`.
    *   *Purpose:* Ensure the service is running and accessible after the `docker-compose.yml` change.

2.  **Execute Test Script & Observe RabbitMQ UI:**
    *   Run the `test_dramatiq_worker.py` script.
    *   Simultaneously monitor the `default` queue (or the specific queue used by the actor) in the RabbitMQ management UI.
    *   Observe:
        *   **Messages:** Arrival state (Ready/Unacked), count.
        *   **Consumers:** Presence (>0), activity status.
    *   *Purpose:* Track the message flow and worker connection status in real-time.

3.  **Analyze Findings:**
    *   Correlate UI observations with script/worker logs.
    *   Determine the failure point based on the analysis flow below.
    *   *Purpose:* Pinpoint whether the issue lies in message sending, broker delivery, worker consumption, or actor invocation.

4.  **Refine Debugging:**
    *   Based on the analysis, plan the next specific debugging actions (e.g., more logs, inspect message content, check worker config).
    *   *Purpose:* Formulate targeted next steps to resolve the identified failure point.

**Conceptual Flow Diagram:**

```mermaid
graph TD
    A[Run test_dramatiq_worker.py] --> B{Sends Message?};
    B -- Yes --> C[Message in RabbitMQ Queue?];
    B -- No --> D[Debug Script Sending Logic];
    C -- Yes --> E{Worker Consuming?};
    C -- No --> F[Debug Broker/Queue Config];
    E -- Yes --> G{Actor Invoked?};
    E -- No --> H[Debug Worker Connection/Subscription];
    G -- Yes --> I{Correct Behavior?};
    G -- No --> J[Debug Actor Internal Logic];
    I -- Yes --> K[Success!];
    I -- No --> J;

    subgraph RabbitMQ UI Checks
        C -- Check --> C1[Messages Ready/Unacked]
        E -- Check --> E1[Consumer Count > 0 & Active]
    end

    subgraph Log Checks
        A -- Check --> L1[Script Logs]
        E -- Check --> L2[Worker Logs]
        G -- Check --> L2
    end

    style D fill:#f9f,stroke:#333,stroke-width:2px
    style F fill:#f9f,stroke:#333,stroke-width:2px
    style H fill:#f9f,stroke:#333,stroke-width:2px
    style J fill:#f9f,stroke:#333,stroke-width:2px
    style K fill:#ccf,stroke:#333,stroke-width:2px
```

**Next Step (After Plan Approval):** Switch to Debug mode to execute this plan.