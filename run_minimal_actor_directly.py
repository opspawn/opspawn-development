import os
import sys
import logging
import pprint
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from pathlib import Path
import time

# --- Configuration ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# --- Logging Setup ---
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)], # Log to stdout for easier capture
)
logger = logging.getLogger(__name__)

# --- Environment Logging ---
logger.info("--- Starting Direct Actor Invocation Script ---")
logger.info(f"Timestamp: {time.time()}")
logger.info(f"Current Working Directory: {os.getcwd()}")
try:
    logger.info(f"User ID: {os.getuid()}, Group ID: {os.getgid()}")
except AttributeError:
    logger.info("UID/GID not available on this platform.")

logger.info("--- Environment Variables ---")
# Use pprint for potentially cleaner multiline output
logger.info(f"\n{pprint.pformat(dict(os.environ))}")

logger.info("--- sys.path ---")
logger.info(f"\n{pprint.pformat(sys.path)}")

# Log modules *before* importing the worker or setting up the broker
logger.info("--- sys.modules (before broker/worker import) ---")
logger.info(f"\n{pprint.pformat(sorted(sys.modules.keys()))}")

# --- Import Target Actor ---
try:
    # Assuming minimal_worker.py is in the same directory or accessible via PYTHONPATH
    logger.info("Importing minimal_worker...")
    import minimal_worker
    logger.info("minimal_worker imported successfully.")
    # Access the underlying function directly
    target_actor_function = minimal_worker.simple_task.fn
    logger.info(f"Target actor function resolved: {target_actor_function}")
except ImportError as e:
    logger.exception("Failed to import minimal_worker or resolve actor function.")
    sys.exit(1)
except AttributeError as e:
    logger.exception("Failed to find 'simple_task' or its '.fn' attribute in minimal_worker.")
    sys.exit(1)

# --- Broker Setup (Manual) ---
# Note: We don't strictly *need* the broker to call .fn,
# but setting it up might reveal differences in library interactions.
# We won't actually *use* it to send/receive for this test.
logger.info(f"Attempting to set up RabbitmqBroker with URL: {RABBITMQ_URL}")
try:
    # Explicitly create a broker instance like the worker might
    broker = RabbitmqBroker(url=RABBITMQ_URL)
    dramatiq.set_broker(broker)
    logger.info("Dramatiq broker set successfully (manual setup).")
    # Optional: Try declaring the actor to see if that triggers anything
    # broker.declare_actor(minimal_worker.simple_task)
    # logger.info("Declared actor on manual broker instance.")
except Exception as e:
    logger.exception("Failed during manual broker setup.")
    # Continue execution to attempt direct call if possible

# --- Direct Actor Function Invocation ---
logger.info("Attempting direct invocation of target_actor_function...")
try:
    # Prepare sample arguments matching the actor's signature
    sample_message = "Direct invocation test message"
    logger.info(f"Invoking with message: '{sample_message}'")

    # Call the underlying function directly
    result = target_actor_function(sample_message)

    logger.info(f"Direct invocation successful. Result: {result}")

except Exception as e:
    logger.exception("Error during direct invocation of actor function.")
    sys.exit(1)

logger.info("--- Direct Actor Invocation Script Finished ---")