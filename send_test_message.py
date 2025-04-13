import os
import sys
import uuid
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- Load .env file FIRST ---
dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)
print(f"INFO: send_test_message: Early .env loading from: {dotenv_path}")

# --- Unset DRAMATIQ_TESTING before broker import ---
if "DRAMATIQ_TESTING" in os.environ:
    del os.environ["DRAMATIQ_TESTING"]
    print("INFO: send_test_message: Unset DRAMATIQ_TESTING in main script env before broker import.")

# --- Setup paths ---
sys.path.insert(0, str(Path(__file__).parent / "ops-core" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "agentkit" / "src"))

# --- Imports ---
try:
    # Import the broker module first to ensure it's configured correctly
    from ops_core.tasks import broker
    # Now import the actor
    from ops_core.scheduler.engine import execute_agent_task_actor
    print(f"INFO: send_test_message: Imported broker ({type(broker.broker).__name__}) and actor.")
except ImportError as e:
    print(f"ERROR: send_test_message: Failed to import modules: {e}")
    sys.exit(1)

# --- Task Details ---
TEST_TASK_ID = f"task_manual_{uuid.uuid4()}"
TEST_GOAL = "Manual test confirmation."
TEST_INPUT_DATA = {"prompt": TEST_GOAL}

# --- Send Message ---
print(f"INFO: send_test_message: Sending message for task {TEST_TASK_ID}...")
message_data = {"task_id": TEST_TASK_ID, "goal": TEST_GOAL, "input_data": TEST_INPUT_DATA}
print(f"INFO: send_test_message: Message data: {message_data}")

try:
    execute_agent_task_actor.send(**message_data)
    print(f"INFO: send_test_message: Message sent successfully for task {TEST_TASK_ID}.")
except Exception as e:
    print(f"ERROR: send_test_message: Failed to send message: {e}")
    sys.exit(1)