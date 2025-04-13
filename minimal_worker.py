import dramatiq
# Import the broker class so the CLI can find it via the name 'broker' below
from dramatiq.brokers.rabbitmq import RabbitmqBroker
# Import default middleware *except* Prometheus
from dramatiq.middleware import AgeLimit, TimeLimit, Callbacks, Retries
import logging
import time
import os
import sys

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - [PID:%(process)d] - %(message)s')
logger = logging.getLogger("minimal_worker")
logger.setLevel(logging.INFO)

logger.critical("!!!!!! minimal_worker.py module top level START !!!!!!")
logger.info(f"Python sys.path: {sys.path}")
logger.info(f"Current working directory: {os.getcwd()}")

# --- Broker Setup ---
# Broker configuration is handled by the dramatiq CLI arguments.
# The CLI needs to find the *name* 'broker' in this module.
# We point it to the class, and explicitly define the middleware *without* Prometheus.
broker = RabbitmqBroker(
    middleware=[
        AgeLimit(),
        TimeLimit(),
        Callbacks(),
        Retries(min_backoff=1000, max_backoff=30000, max_retries=3), # Example retry config
        # Prometheus() middleware is omitted
    ]
)
logger.info(f"Defined 'broker' variable pointing to broker instance (Prometheus disabled): {broker}")
# We DO NOT call dramatiq.set_broker() here. The CLI uses the 'broker' variable.

# --- Actor Definition ---
logger.info("!!!!!! Defining simple_task actor (implicitly finding broker) !!!!!!")
# Rely on Dramatiq finding the broker set globally by the CLI
@dramatiq.actor
def simple_task(message: str):
    """A simple actor that logs the received message."""
    actor_logger = getattr(simple_task, "logger", logger)
    actor_logger.info("!!!!!! simple_task actor function entered !!!!!!")
    actor_logger.info(f"!!!!!! MINIMAL WORKER RECEIVED MESSAGE: {message} !!!!!!")
    print(f"Minimal worker processed: {message}") # Also print to stdout

logger.info(f"!!!!!! simple_task actor defined: {simple_task} !!!!!!")

logger.info("Minimal worker module loaded. Waiting for tasks...")
logger.critical("!!!!!! minimal_worker.py module top level END !!!!!!")