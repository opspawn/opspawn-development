import os
import logging
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
# Import the actual broker instance from ops_core
# This ensures the sender uses the same configuration as the worker
from ops_core.tasks import broker as ops_core_broker # Renamed to avoid conflict
# Import the target actor function
from ops_core.scheduler.engine import execute_agent_task_actor

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get RabbitMQ URL from environment variable, default if not set
rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
logger.info(f"Using RabbitMQ URL for sending: {rabbitmq_url}")

# Set the imported broker globally for Dramatiq
# This is crucial for .send() to work correctly
dramatiq.set_broker(ops_core_broker.broker)
logger.info(f"Set global broker for sending: {ops_core_broker.broker}")

# No need to re-declare the actor, just use the imported one
# sender_task_actor = dramatiq.actor(broker=sender_broker)(simple_task_function) # REMOVED
# logger.info(f"Explicitly declared sender actor '{sender_task_actor.actor_name}' on sender broker.") # REMOVED

# Send a test message using the sender-specific actor
# Prepare arguments for execute_agent_task_actor
test_task_id = "test_task_001"
test_goal = "Test goal from sender script"
test_input_data = {"param1": "value1", "details": "Sent via send_test_message_clean_env.py"}

logger.info(f"Sending message to actor {execute_agent_task_actor.actor_name} on queue {execute_agent_task_actor.queue_name}")
logger.info(f"  task_id: {test_task_id}")
logger.info(f"  goal: {test_goal}")
logger.info(f"  input_data: {test_input_data}")

# Send the message using the imported actor
execute_agent_task_actor.send(
    task_id=test_task_id,
    goal=test_goal,
    input_data=test_input_data
)

logger.info("Message sent.")

# Optional: Add a small delay to allow the message to be processed before exiting
# import time
# time.sleep(2)
# logger.info("Sender finished.")