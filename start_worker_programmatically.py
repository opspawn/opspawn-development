import os
import asyncio
import logging
import os
import time

import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.middleware import AsyncIO
from dramatiq.worker import Worker

# Configure logging - Set root logger to DEBUG to capture everything
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - [PID:%(process)d] - %(message)s')
logger = logging.getLogger(__name__)
# Ensure our own logger is at least INFO if needed, but root is DEBUG
# logger.setLevel(logging.INFO)

# Import the raw actor *function* from the minimal worker file
# Ensure minimal_worker.py is in the Python path or same directory
try:
    # We need the function itself, not the decorated actor object
    from minimal_worker import simple_task as simple_task_function
    logger.info("Successfully imported simple_task function from minimal_worker.")
except ImportError as e:
    logger.error(f"Failed to import simple_task function from minimal_worker: {e}")
    logger.error("Ensure minimal_worker.py is in the current directory or Python path.")
    exit(1)

# Get RabbitMQ URL from environment variable, default if not set
rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
logger.info(f"Using RabbitMQ URL: {rabbitmq_url}")

# --- Programmatic Worker Setup ---
# 1. Instantiate a new broker instance here
programmatic_broker = RabbitmqBroker(url=rabbitmq_url)
logger.info(f"Created new programmatic broker instance: {programmatic_broker}")

# 2. Add middleware (Add AsyncIO back)
programmatic_broker.add_middleware(AsyncIO())
# Add other necessary middleware if needed (e.g., Retries)
# programmatic_broker.add_middleware(Retries())
logger.info("Added AsyncIO middleware to programmatic broker.")

# 3. Explicitly declare the actor on our new broker instance
#    Use the imported raw function (simple_task_function)
simple_task_actor = dramatiq.actor(broker=programmatic_broker)(simple_task_function.fn)
logger.info(f"Explicitly declared actor '{simple_task_actor.actor_name}' on programmatic broker.")
logger.info(f"Actor '{simple_task_actor.actor_name}' is declared on broker: {simple_task_actor.actor_name in programmatic_broker.actors}")

# 4. Instantiate the Worker
#    Pass the configured broker instance and explicitly specify the queue(s) to consume.
#    The default queue for simple_task_actor is 'simple_task'.
worker = Worker(programmatic_broker, worker_threads=1, queues=[simple_task_actor.queue_name])
logger.info("Worker instance created.")

# 5. Run the worker directly (worker.join() is blocking)
if __name__ == "__main__":
    logger.info("Starting worker programmatically...")
    logger.info(f"Broker state before start/join: {programmatic_broker}")
    logger.info(f"Broker connected? {programmatic_broker.connection is not None and not programmatic_broker.connection.is_closed}")
    logger.info(f"Actors declared on broker: {programmatic_broker.actors}")
    logger.info("Pausing for 1 second before start/join...")
    time.sleep(1) # Add a small delay
    try:
        # worker.start() starts the worker threads/processes first
        worker.start()
        logger.info("Called worker.start()")
        # worker.join() then waits for them to complete.
        worker.join()
    except KeyboardInterrupt:
        # This block might not even be reached if worker.join() handles SIGINT cleanly.
        logger.info("KeyboardInterrupt received during worker.join().")
        # worker.join() should handle graceful shutdown on SIGINT/KeyboardInterrupt
    finally:
        # Assuming worker.join() handles broker connection cleanup on exit.
        # Add explicit broker.close() here only if necessary based on testing.
        logger.info("Programmatic worker shutdown complete.")