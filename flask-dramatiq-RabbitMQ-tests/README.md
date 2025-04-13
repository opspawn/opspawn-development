# Minimal Flask + Dramatiq + RabbitMQ Test Case

This project provides a very simple demonstration of integrating Flask with Dramatiq for background task processing using RabbitMQ as the message broker.

## Purpose

The goal is to isolate the core interaction between a web API (Flask), a task queue system (Dramatiq), and a message broker (RabbitMQ) in the simplest way possible. This helps in understanding the fundamental setup and debugging potential issues related to worker invocation or message passing.

## Setup

1.  **RabbitMQ:**
    You need a running RabbitMQ instance. The application is configured to connect to `amqp://guest:guest@localhost:5672/`. You can start one easily using Docker:
    ```bash
    docker run -d --hostname my-rabbit --name minimal-test-rabbit -p 5672:5672 -p 15672:15672 rabbitmq:3-management
    ```
    *(Note: If port 15672 is already in use, you can change the host port, e.g., `-p 15673:15672`)*

2.  **Python Environment:**
    It's recommended to use a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```

3.  **Dependencies:**
    Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

You need to run two separate processes: the Dramatiq worker and the Flask API server. Open two terminals in the project directory (`flask-dramatiq-RabbitMQ-tests/`).

1.  **Terminal 1: Start the Worker**
    Make the script executable (if needed) and run it:
    ```bash
    chmod +x run_worker.sh
    ./run_worker.sh
    ```
    You should see output indicating the worker is running and watching the `app` module.

2.  **Terminal 2: Start the API Server**
    Make the script executable (if needed) and run it:
    ```bash
    chmod +x run_api.sh
    ./run_api.sh
    ```
    You should see output indicating the Flask server is running on `http://0.0.0.0:5001/`.

## Testing

Once both the worker and the API server are running:

1.  **Submit a Task:**
    Open a third terminal or use a tool like `curl` or Postman to send a POST request to the API. Replace `10` with the desired number of seconds for the task to simulate work.
    ```bash
    curl -X POST http://localhost:5001/submit/10
    ```

2.  **Observe Output:**
    *   **API Terminal:** You should see logs indicating the request was received and the task was sent. The `curl` command will receive a JSON response like `{"message_id": "...", "status": "submitted", "value": 10}`.
    *   **Worker Terminal:** You should see logs indicating the task was received, the countdown messages, and finally the completion message.

## Stopping

-   Press `Ctrl+C` in the API and Worker terminals to stop the processes.
-   Stop the RabbitMQ container if you started it with Docker: `docker stop minimal-test-rabbit`