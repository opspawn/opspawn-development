import os # Added
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.brokers.stub import StubBroker # Added
from dramatiq.middleware import AsyncIO # Import AsyncIO middleware
from dramatiq.results import Results # Import the Results middleware
from dramatiq.results.backends.stub import StubBackend # Import a backend (Stub for now)

# Configure the broker based on environment
if os.getenv("DRAMATIQ_TESTING") == "1":
    broker = StubBroker()
    broker.emit_after("process_boot") # Recommended for StubBroker
    dramatiq.set_broker(broker) # Set StubBroker globally
    # print("!!! BROKER CONFIGURED: StubBroker !!!") # Removed debug print

    # Add middleware for the StubBroker
    # results_backend = StubBackend() # Removed Results middleware
    # broker.add_middleware(Results(backend=results_backend)) # Removed Results middleware
    broker.add_middleware(AsyncIO()) # Keep AsyncIO middleware
else:
    # Configure the RabbitMQ broker connection
    # Assumes RabbitMQ is running on localhost:5672 with default credentials (guest/guest)
    # TODO: Make broker URL configurable (e.g., via environment variables)
    # Removed explicit url, relying on defaults (amqp://guest:guest@localhost:5672)
    # Configure RabbitMQ only if not testing
    broker = RabbitmqBroker()
    broker.declare_queue("default") # Explicitly declare the default queue for RabbitMQ
    dramatiq.set_broker(broker) # Set RabbitmqBroker globally
    # print("!!! BROKER CONFIGURED: RabbitmqBroker !!!") # Removed debug print

    # Add middleware for the RabbitMQ broker
    # results_backend = StubBackend() # Removed Results middleware
    # broker.add_middleware(Results(backend=results_backend)) # Removed Results middleware
    broker.add_middleware(AsyncIO()) # Restore AsyncIO middleware

# dramatiq.set_broker(broker) # Set the chosen broker globally - REMOVED, moved into if/else

# Optional: Configure other Dramatiq settings if needed
# dramatiq.set_encoder(...)

# Middleware additions moved into the if/else blocks above.
