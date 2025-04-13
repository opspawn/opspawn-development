import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# --- Load .env file FIRST ---
# Load .env file from the root directory before any other imports
# that might trigger config loading (like sql_store)
dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)
print(f"INFO: Early .env loading from: {dotenv_path}") # Add print for confirmation

# --- Now other imports ---
import asyncio
import subprocess
# Imports for Alembic programmatic execution added
from alembic.config import Config
from alembic import command, context as alembic_context # Import context
from sqlalchemy import create_engine # Import synchronous engine
# from ops_core.models.base import metadata as target_metadata # No longer needed here, loaded dynamically
import time
import uuid
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_dramatiq_worker")

# Ensure ops_core and agentkit are importable (adjust if needed based on execution context)
# This assumes running from the root '1-t' directory
# Add both ops-core/src and ops-core to sys.path
# src is needed for models, config etc.
# src paths are needed for models, config etc.
sys.path.insert(0, str(Path(__file__).parent / "ops-core" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "agentkit" / "src"))
# We will load alembic.env directly later, so no need to add ops-core to path here.

# --- Unset DRAMATIQ_TESTING before broker import ---
# This ensures the main script uses RabbitmqBroker for sending
if "DRAMATIQ_TESTING" in os.environ:
    del os.environ["DRAMATIQ_TESTING"]
    print("INFO: Unset DRAMATIQ_TESTING in main script env before broker import.")

# --- Imports (after path setup and env var unset) ---
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
# .env is already loaded at the top
logger.info(f".env file was loaded early from: {dotenv_path}")

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

WORKER_STARTUP_WAIT = 5 # seconds to wait for worker process to initialize (Increased)
TASK_COMPLETION_WAIT = 15 # seconds (longer than agent timeout + buffer)

# Removed importlib.util as we revert to command.upgrade

def run_sync_migrations():
    """Runs Alembic migrations using a synchronous connection."""
    logger.info("Running Alembic migrations synchronously...")
    alembic_cfg = Config(str(Path(__file__).parent / "ops-core" / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(Path(__file__).parent / "ops-core" / "alembic"))
    # Note: command.upgrade will use the URL from alembic.ini or env.py,
    # which should resolve to the correct DATABASE_URL from .env
    # alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL) # Not needed when calling command.upgrade

    try:
        # Let Alembic handle the connection and context via command.upgrade
        # It should use the synchronous psycopg2 driver if available and configured correctly in env.py logic (which it isn't explicitly, but command might handle it)
        # or potentially fail if it tries to use asyncpg synchronously.
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations completed successfully via command.upgrade.")
    except Exception as alembic_err:
        logger.error(f"Alembic migration failed via command.upgrade: {alembic_err}", exc_info=True)
        raise RuntimeError("Alembic migration failed.") from alembic_err
    # No engine/connection to dispose here as command.upgrade handles it internally
 
# Removed duplicate run_sync_migrations function definition
async def main():
    logger.info("--- Starting Dramatiq Worker Isolation Test ---")
    session = None
    worker_process = None

    # Migrations are now run synchronously before main()
    try:
        # 1. Start worker in subprocess FIRST
        worker_env = os.environ.copy() # Pass environment
        # Keep inherited PYTHONPATH from tox environment
        logger.info(f"Inheriting PYTHONPATH for worker subprocess: {worker_env.get('PYTHONPATH')}")
        # Explicitly pass LLM config env vars (and API keys if necessary)
        llm_provider = os.getenv("AGENTKIT_LLM_PROVIDER", "google") # Get from main env or default
        llm_model = os.getenv("AGENTKIT_LLM_MODEL", "gemini-2.5-pro-exp-03-25") # Get from main env or default
        worker_env["AGENTKIT_LLM_PROVIDER"] = llm_provider
        worker_env["AGENTKIT_LLM_MODEL"] = llm_model
        for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"]:
             if key in os.environ:
                  worker_env[key] = os.environ[key]
        logger.info(f"Setting AGENTKIT_LLM_PROVIDER for worker: {llm_provider}")
        logger.info(f"Setting AGENTKIT_LLM_MODEL for worker: {llm_model}")
        logger.info(f"Passing API keys if set: {' '.join([k for k in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'OPENROUTER_API_KEY'] if k in worker_env])}")
        # Ensure DRAMATIQ_TESTING is NOT set for the worker
        if "DRAMATIQ_TESTING" in worker_env:
            del worker_env["DRAMATIQ_TESTING"]
            logger.info("Removed DRAMATIQ_TESTING=1 from worker environment to force RabbitmqBroker.")
        cmd = [
            sys.executable, # Use the same python interpreter
            "-m", "dramatiq",
            "ops_core.tasks.broker:broker",
            "ops_core.tasks.worker",
        ]
        logger.info(f"Starting worker subprocess with command: {' '.join(cmd)}")
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

        # 2. Setup DB connection and create task
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
        message_data = {"task_id": TEST_TASK_ID, "goal": TEST_GOAL, "input_data": TEST_INPUT_DATA}
        logger.info(f"VERBOSE_LOG: Sending message data: {message_data}")
        execute_agent_task_actor.send(**message_data)
        logger.info("Message sent.")
        logger.info(f"VERBOSE_LOG: Message sent for task {TEST_TASK_ID} via broker {type(broker.broker).__name__}")

        # 4. Wait for task completion (or timeout) - Renumbered from 5
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

            await asyncio.sleep(1) # Poll interval (reduced)
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


        # --- Instructions for Manual Worker Test ---
        # logger.info("="*50)
        # logger.info("MANUAL WORKER TEST INSTRUCTIONS:")
        # logger.info(f"1. A message for task ID '{TEST_TASK_ID}' has been sent to RabbitMQ.")
        # logger.info("2. Open a NEW terminal in the '/home/sf2/Workspace/23-opspawn/1-t' directory.")
        # logger.info("3. Ensure Docker containers (RabbitMQ, DB) are running (`docker compose up -d`).")
        # logger.info("4. Run the following command in the new terminal to start the worker:")
        # logger.info("   tox exec -e py312 -- env DRAMATIQ_TESTING= python -m dramatiq ops_core.tasks.broker:broker ops_core.tasks.worker --verbose")
        # logger.info("5. Observe the worker logs in the new terminal. Look for processing related to the task ID above.")
        # logger.info("6. Check the database manually (or re-run this script later with polling restored) to see if the task status changes from PENDING.")
        # logger.info("="*50)

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