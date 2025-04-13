import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
import logging
import time
import os

# Basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("minimal_worker")

# Configure broker (use RabbitMQ if URL is set, otherwise default)
# Note: Dramatiq worker CLI usually handles broker setup based on args/env,
# but we define it here for clarity in this minimal example.
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
if RABBITMQ_URL:
    logger.info(f"Configuring RabbitmqBroker with URL: {RABBITMQ_URL}")
    broker = RabbitmqBroker(url=RABBITMQ_URL)
else:
    logger.warning("RABBITMQ_URL not set, using default localhost.")
    broker = RabbitmqBroker()

dramatiq.set_broker(broker)

@dramatiq.actor
def simple_task(message: str):
    """A simple actor that logs the received message."""
    logger.critical(f"!!!!!! MINIMAL WORKER RECEIVED MESSAGE: {message} !!!!!!")
    print(f"Minimal worker processed: {message}") # Also print to stdout

logger.info("Minimal worker module loaded. Waiting for tasks...")
# When run via 'dramatiq minimal_worker', Dramatiq CLI handles the rest.