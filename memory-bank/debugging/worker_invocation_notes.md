# Debugging Note: Correct Manual Invocation for Dramatiq Worker

**Date:** 2025-04-13

**Context:** During debugging of Task 7.2, it was discovered that invoking the Dramatiq worker using standard methods like `dramatiq ...` or `tox exec -- dramatiq ...` within the project's root `tox` environment is unreliable and prevents the worker from processing messages correctly.

**Problem:** These invocation methods seem to interfere with the worker's environment setup or process handling, leading to silent failures where the worker starts but doesn't consume tasks from the queue.

**Solution:** The reliable method to run the worker manually for debugging purposes (using the dependencies defined in the root `tox.ini`) is to directly execute the Python interpreter located within the root `.tox` environment and run the `dramatiq` module.

**Correct Command (Run from project root `/home/sf2/Workspace/23-opspawn/1-t`):**

```bash
.tox/py/bin/python -m dramatiq ops_core.tasks.worker --verbose
```

**Explanation:**

*   `.tox/py/bin/python`: Specifies the exact Python executable created by `tox` in the root project directory. Using this ensures the correct interpreter and all installed dependencies from the `tox` environment are used.
*   `-m dramatiq`: Runs the `dramatiq` library as a module, which is the standard way to invoke its CLI functionality when using a specific interpreter.
*   `ops_core.tasks.worker`: Specifies the Python module path where the Dramatiq actors and broker are discovered.
*   `--verbose`: (Optional but recommended for debugging) Increases logging verbosity.

**Note:** Ensure required services like RabbitMQ and PostgreSQL are running before executing this command.