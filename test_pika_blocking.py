import pika
import os
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - [PID:%(process)d] - %(message)s')
logger = logging.getLogger(__name__)

# Get RabbitMQ URL from environment variable, default if not set
rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
logger.info(f"Attempting to connect to RabbitMQ using BlockingConnection: {rabbitmq_url}")

connection = None
try:
    parameters = pika.URLParameters(rabbitmq_url)
    logger.debug("Creating BlockingConnection...")
    # This is the call that failed within Dramatiq's broker setup
    connection = pika.BlockingConnection(parameters)
    logger.info("Successfully created BlockingConnection.")

    logger.debug("Opening channel...")
    channel = connection.channel()
    logger.info("Successfully opened channel.")

    queue_name = 'default'
    logger.debug(f"Declaring queue: {queue_name}")
    channel.queue_declare(queue=queue_name, durable=True)
    logger.info(f"Successfully declared queue: {queue_name}")

    logger.info("Pika BlockingConnection test successful!")

except RuntimeError as e:
    logger.error(f"Caught RuntimeError during Pika BlockingConnection test: {e}", exc_info=True)
    sys.exit(1) # Exit with error code if the specific runtime error occurs
except Exception as e:
    logger.error(f"Caught unexpected exception during Pika BlockingConnection test: {e}", exc_info=True)
    sys.exit(1)
finally:
    if connection and connection.is_open:
        logger.debug("Closing connection.")
        connection.close()
        logger.info("Connection closed.")
    else:
        logger.warning("Connection was not established or already closed.")

logger.info("Test script finished.")