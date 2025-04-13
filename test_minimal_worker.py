import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_minimal_worker")

# Import the minimal worker's actor for sending messages
# Ensure the current directory is in the path for the import
sys.path.insert(0, str(Path(__file__).parent))
try:
    from minimal_worker import simple_task, broker as minimal_broker
except ImportError as e:
    logger.error(f"Failed to import from minimal_worker.py: {e}")
    logger.error("Ensure minimal_worker.py is in the same directory.")
    sys.exit(1)

# Configuration
WORKER_STARTUP_WAIT = 5 # seconds
MESSAGE_WAIT = 10 # seconds to wait for message processing

def main():
    logger.info("--- Starting Minimal Worker Subprocess Test ---")
    worker_process = None

    try:
        # 1. Start minimal worker in subprocess
        # Use a minimal environment, ensuring PATH is present
        worker_env = {}
        essential_vars = ["PATH", "HOME", "LANG", "TERM", "RABBITMQ_URL"]
        for var in essential_vars:
            value = os.getenv(var)
            if value is not None:
                worker_env[var] = value
            else:
                 logger.warning(f"Essential variable '{var}' not found in parent environment for minimal worker.")
        # Add current dir to PYTHONPATH for worker imports if needed, though minimal_worker is simple
        # worker_env["PYTHONPATH"] = "."

        cmd = [
            sys.executable, # Use the same python interpreter from tox env
            "-m", "dramatiq",
            "minimal_worker:broker", # Point to the broker instance in the minimal worker file
            "minimal_worker",      # The module containing actors
        ]
        logger.info(f"Starting minimal worker subprocess with command: {' '.join(cmd)}")
        worker_process = subprocess.Popen(
            cmd,
            env=worker_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path(__file__).parent) # Run from current dir
        )

        logger.info(f"Waiting {WORKER_STARTUP_WAIT}s for minimal worker to initialize...")
        time.sleep(WORKER_STARTUP_WAIT)

        # Check if worker started okay
        if worker_process.poll() is not None:
            stdout, stderr = worker_process.communicate()
            logger.error(f"Minimal Worker process terminated prematurely! Exit code: {worker_process.returncode}")
            logger.error(f"Minimal Worker STDOUT:\n{stdout}")
            logger.error(f"Minimal Worker STDERR:\n{stderr}")
            raise RuntimeError("Minimal Worker failed to start.")
        else:
            logger.info("Minimal Worker process appears to be running.")

        # 2. Send message to the simple_task actor
        test_message = f"Hello from test_minimal_worker at {time.time()}"
        logger.info(f"Sending message to actor 'simple_task': '{test_message}'...")
        simple_task.send(test_message)
        logger.info("Message sent to minimal worker.")

        # 3. Wait a bit to see if the message gets processed
        logger.info(f"Waiting {MESSAGE_WAIT}s for message processing...")
        time.sleep(MESSAGE_WAIT)
        logger.info("Finished waiting.")

    except Exception as e:
        logger.exception(f"An error occurred during the minimal test: {e}")
    finally:
        # 4. Cleanup
        logger.info("--- Cleaning up minimal worker ---")
        if worker_process and worker_process.poll() is None:
            logger.info("Terminating minimal worker process...")
            worker_process.terminate()
            stdout = None
            stderr = None
            try:
                stdout, stderr = worker_process.communicate(timeout=5)
                logger.info(f"Minimal Worker process terminated gracefully (return code: {worker_process.returncode}).")
            except subprocess.TimeoutExpired:
                logger.warning("Minimal Worker process did not terminate gracefully after 5s, killing.")
                worker_process.kill()
                stdout, stderr = worker_process.communicate()
                logger.info(f"Minimal Worker process killed (return code: {worker_process.returncode}).")
            except Exception as comm_err:
                 logger.error(f"Error communicating with minimal worker process during termination: {comm_err}")

            # Log captured output
            if stdout:
                logger.info(f"--- Minimal Worker STDOUT ---\n{stdout}\n--- End Minimal Worker STDOUT ---")
            else:
                logger.info("--- Minimal Worker STDOUT: (empty) ---")
            if stderr:
                logger.info(f"--- Minimal Worker STDERR ---\n{stderr}\n--- End Minimal Worker STDERR ---")
            else:
                logger.info("--- Minimal Worker STDERR: (empty) ---")

    logger.info("--- Minimal Test Finished ---")

if __name__ == "__main__":
    main() # No async needed here