import asyncio
import os
import subprocess
# Imports for Alembic programmatic execution added
from alembic.config import Config
from alembic import command, context as alembic_context # Import context
from sqlalchemy import create_engine # Import synchronous engine
from ops_core.models.base import metadata as target_metadata # Import metadata for sync run
import sys
import time
import uuid
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_dramatiq_worker")

# Ensure ops_core and agentkit are importable (adjust if needed based on execution context)
# This assumes running from the root '1-t' directory
sys.path.insert(0, str(Path(__file__).parent / "ops-core" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "agentkit" / "src"))

# --- Imports (after path setup) ---
try:
    from ops_core.models.tasks import Task, TaskStatus
    from ops_core.metadata.sql_store import SqlMetadataStore, AsyncSessionFactory # Corrected import name
    from ops_core.scheduler.engine import execute_agent_task_actor
    from ops_core.tasks import broker # Needed to ensure broker is configured before sending
except ImportError as e:
    logger.error(f"Failed to import necessary modules: {e}")
    logger.error("Ensure you run this script from the workspace root directory '1-t'.")
    sys.exit(1)

# --- Configuration ---
# Load .env file from the root directory
dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)
logger.info(f"Loaded .env file from: {dotenv_path}")

DATABASE_URL = os.getenv("DATABASE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL") # Dramatiq worker reads this internally

if not DATABASE_URL:
    logger.error("DATABASE_URL not found in environment or .env file.")
    sys.exit(1)
if not RABBITMQ_URL:
    logger.warning("RABBITMQ_URL not found, worker will use Dramatiq default (amqp://guest:guest@localhost:5672/).")

# Task details
TEST_TASK_ID = f"task_{uuid.uuid4()}"
TEST_GOAL = "Write a short confirmation message."
TEST_INPUT_DATA = {"prompt": TEST_GOAL} # Match input structure if needed

WORKER_STARTUP_WAIT = 5 # seconds to wait for worker process to initialize
TASK_COMPLETION_WAIT = 70 # seconds (includes agent timeout + buffer)

def run_sync_migrations():
    """Runs Alembic migrations using a synchronous connection."""
    logger.info("Running Alembic migrations synchronously...")
    alembic_cfg = Config(str(Path(__file__).parent / "ops-core" / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(Path(__file__).parent / "ops-core" / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL) # Use URL from .env
 
    engine = None
    try:
        engine = create_engine(DATABASE_URL)
        # Run upgrade command directly, no need for context configuration here
        # env.py handles context configuration when command.upgrade is called
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations completed successfully (synchronous).")
    except Exception as alembic_err:
        logger.error(f"Alembic migration failed (synchronous): {alembic_err}", exc_info=True)
        raise RuntimeError("Alembic migration failed.") from alembic_err
    finally:
        if engine:
            engine.dispose()
            logger.info("Synchronous engine disposed.")
 
# Removed duplicate run_sync_migrations function definition
async def main():
    logger.info("--- Starting Dramatiq Worker Isolation Test ---")
    session = None
    worker_process = None

    # Migrations are now run synchronously before main()
    try:
        # 1. Setup DB connection and create task
        logger.info("Connecting to database and creating test task...")
        session = AsyncSessionFactory() # Use correct factory name
        metadata_store = SqlMetadataStore(session)

        test_task = Task(
            task_id=TEST_TASK_ID,
            name="Isolation Test Task",
            task_type="agent_run",
            input_data=TEST_INPUT_DATA,
            status=TaskStatus.PENDING,
        )
        await metadata_store.add_task(test_task)
        logger.info(f"Test task {TEST_TASK_ID} created in DB with status PENDING.")

        # 3. Send message to actor
        logger.info(f"Sending message to actor 'execute_agent_task_actor' for task {TEST_TASK_ID}...")
        # Ensure the broker is the correct one (RabbitMQ)
        if not isinstance(broker.broker, broker.RabbitmqBroker):
             logger.warning(f"Broker is not RabbitmqBroker ({type(broker.broker)}), sending might fail in live env.")
        execute_agent_task_actor.send(task_id=TEST_TASK_ID, goal=TEST_GOAL, input_data=TEST_INPUT_DATA)
        logger.info("Message sent.")

        # 4. Start worker in subprocess
        worker_env = os.environ.copy() # Pass environment
        cmd = [
            sys.executable, # Use the same python interpreter
            "-m", "dramatiq",
            "ops_core.tasks.broker:broker",
            "ops_core.tasks.worker",
            "--verbose", # Add verbosity
            "--logs-config", "/dev/null" # Prevent Dramatiq from overriding logging basicConfig
        ]
        logger.info(f"Starting worker subprocess with command: {' '.join(cmd)}")
        # Capture stdout/stderr
        worker_process = subprocess.Popen(
            cmd,
            env=worker_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        logger.info(f"Waiting {WORKER_STARTUP_WAIT}s for worker to initialize...")
        time.sleep(WORKER_STARTUP_WAIT)

        # Check if worker started okay
        if worker_process.poll() is not None:
            stdout, stderr = worker_process.communicate()
            logger.error(f"Worker process terminated prematurely! Exit code: {worker_process.returncode}")
            logger.error(f"Worker STDOUT:\n{stdout}")
            logger.error(f"Worker STDERR:\n{stderr}")
            raise RuntimeError("Worker failed to start.")
        else:
            logger.info("Worker process appears to be running.")

        # 5. Wait for task completion (or timeout)
        logger.info(f"Waiting up to {TASK_COMPLETION_WAIT}s for task {TEST_TASK_ID} to complete...")
        start_wait_time = time.time()
        final_status = TaskStatus.PENDING
        while time.time() - start_wait_time < TASK_COMPLETION_WAIT:
            try:
                task = await metadata_store.get_task(TEST_TASK_ID)
                final_status = task.status
                if final_status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    logger.info(f"Task {TEST_TASK_ID} reached terminal status: {final_status}")
                    break
                else:
                    logger.info(f"Task {TEST_TASK_ID} status: {final_status}. Waiting...")
            except TaskNotFoundError:
                logger.warning(f"Task {TEST_TASK_ID} not found during polling (might be race condition?). Waiting...")
            except Exception as e:
                 logger.exception(f"Error polling task status: {e}")

            await asyncio.sleep(5) # Poll interval
        else:
            logger.warning(f"Task {TEST_TASK_ID} did not complete within {TASK_COMPLETION_WAIT}s timeout. Final polled status: {final_status}")

        # 6. Check final status again after wait
        try:
            task = await metadata_store.get_task(TEST_TASK_ID)
            final_status = task.status
            logger.info(f"Final check: Task {TEST_TASK_ID} status in DB: {final_status}")
            if final_status == TaskStatus.FAILED:
                 logger.info(f"Task error message: {task.error_message}")
                 logger.info(f"Task result: {task.result}")
            elif final_status == TaskStatus.COMPLETED:
                 logger.info(f"Task result: {task.result}")

        except Exception as e:
            logger.exception(f"Error getting final task status: {e}")


    except Exception as e:
        logger.exception(f"An error occurred during the test: {e}")
    finally:
        # 7. Cleanup
        logger.info("--- Cleaning up ---")
        if worker_process and worker_process.poll() is None:
            logger.info("Terminating worker process...")
            worker_process.terminate()
            try:
                stdout, stderr = worker_process.communicate(timeout=5)
                logger.info("Worker process terminated.")
                logger.info(f"Worker STDOUT:\n{stdout}")
                logger.info(f"Worker STDERR:\n{stderr}")
            except subprocess.TimeoutExpired:
                logger.warning("Worker process did not terminate gracefully, killing.")
                worker_process.kill()
                stdout, stderr = worker_process.communicate()
                logger.info(f"Worker STDOUT:\n{stdout}")
                logger.info(f"Worker STDERR:\n{stderr}")

        if session:
            logger.info("Closing database session.")
            await session.close()

    logger.info("--- Test Finished ---")
if __name__ == "__main__":
    # Run migrations synchronously first
    run_sync_migrations()
    # Then run the async main function
    asyncio.run(main())
# Removed duplicate if __name__ == "__main__": block