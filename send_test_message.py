import os
import sys
import uuid
import logging
from pathlib import Path
from dotenv import load_dotenv
import time # Add time for unique message

# --- Load .env file FIRST ---
dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)
print(f"INFO: send_test_message: Early .env loading from: {dotenv_path}")

# --- Unset DRAMATIQ_TESTING before broker import ---
if "DRAMATIQ_TESTING" in os.environ:
    del os.environ["DRAMATIQ_TESTING"]
    print("INFO: send_test_message: Unset DRAMATIQ_TESTING in main script env before broker import.")

# --- Imports ---
try:
    # Import the minimal worker module to get its broker and actor
    # Importing minimal_worker will also execute its dramatiq.set_broker() call
    import minimal_worker
    print(f"INFO: send_test_message: Imported minimal_worker module.")
    print(f"INFO: send_test_message: Using broker configured by minimal_worker: {type(minimal_worker.broker).__name__}")

except ImportError as e:
    print(f"ERROR: send_test_message: Failed to import minimal_worker: {e}")
    sys.exit(1)
except AttributeError:
    # Handle case where minimal_worker might not have broker attribute if not run correctly
    print(f"ERROR: send_test_message: Could not access broker in minimal_worker. Ensure it defines and sets the broker.")
    sys.exit(1)


# --- Task Details ---
TEST_MESSAGE = f"Hello Minimal Worker from send_test_message.py at {time.time()}"

# --- Send Message ---
print(f"INFO: send_test_message: Sending message: '{TEST_MESSAGE}'...")

try:
    # Call send() on the imported actor object
    minimal_worker.simple_task.send(TEST_MESSAGE)
    print(f"INFO: send_test_message: Message sent successfully.")
except Exception as e:
    print(f"ERROR: send_test_message: Failed to send message: {e}")
    sys.exit(1)