"""
Dramatiq worker entry point for Ops Core.

This script imports the necessary broker configuration and task actors
so that the Dramatiq worker process can discover and execute tasks.

To run the worker, use the Dramatiq CLI:
dramatiq ops_core.tasks.worker
"""

import logging

# Configure logging for the worker (optional but recommended)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("VERBOSE_LOG: Initializing Dramatiq worker...")

# Import the broker configuration. This sets up the connection
# and allows Dramatiq to find the broker.
logger.info("VERBOSE_LOG: Importing broker...")
from . import broker # noqa: F401 - Imported for side effects (broker registration)
logger.info(f"VERBOSE_LOG: Broker imported: {broker}")

# Import modules containing Dramatiq actors so they are discovered.
logger.info("VERBOSE_LOG: Importing engine (for actor discovery)...")
from ops_core.scheduler import engine # noqa: F401 - Imports execute_agent_task_actor (Removed src. prefix)
logger.info(f"VERBOSE_LOG: Engine imported: {engine}")
# Check if actor is registered after import
_broker_instance = broker.broker # Get the actual broker instance
_actor_name = "execute_agent_task_actor"
if _actor_name in _broker_instance.actors:
    logger.info(f"VERBOSE_LOG: Actor '{_actor_name}' FOUND in broker registry after engine import.")
else:
    logger.warning(f"VERBOSE_LOG: Actor '{_actor_name}' NOT FOUND in broker registry after engine import!")

logger.info("VERBOSE_LOG: Dramatiq worker module initialization complete.")
logger.info(f"VERBOSE_LOG: Final Broker instance type: {type(broker.broker).__name__}")

# The Dramatiq CLI will handle the rest (connecting, processing tasks)
