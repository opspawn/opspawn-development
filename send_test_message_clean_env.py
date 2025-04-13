import os
import logging
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.middleware import AsyncIO
from minimal_worker import simple_task as simple_task_function # Import the raw function

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get RabbitMQ URL from environment variable, default if not set
rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
logger.info(f"Using RabbitMQ URL for sending: {rabbitmq_url}")

# Explicitly configure the broker for the sender, matching the worker's config
# This ensures queue declaration parameters match.
from dramatiq.middleware import AsyncIO
sender_broker = RabbitmqBroker(url=rabbitmq_url)
sender_broker.add_middleware(AsyncIO()) # Match worker middleware
dramatiq.set_broker(sender_broker)
logger.info(f"Set explicit broker instance for sending: {sender_broker}")

# Explicitly declare the actor on the sender_broker using the imported function
sender_task_actor = dramatiq.actor(broker=sender_broker)(simple_task_function)
logger.info(f"Explicitly declared sender actor '{sender_task_actor.actor_name}' on sender broker.")

# Send a test message using the sender-specific actor
message_data = {"content": "Hello from clean env sender!"}
logger.info(f"Sending message: {message_data} to actor {sender_task_actor.actor_name} on queue {sender_task_actor.queue_name}")
sender_task_actor.send(message_data)

logger.info("Message sent.")

# Optional: Add a small delay to allow the message to be processed before exiting
# import time
# time.sleep(2)
# logger.info("Sender finished.")