#!/bin/bash
WRAPPER_LOG="/tmp/worker_wrapper_log.txt"

# Attempt to create/overwrite the log file and write a single line
echo "Wrapper script executed: $(date)" > "$WRAPPER_LOG"
EXIT_CODE=$?

# Exit with the exit code of the echo command (0 if successful)
exit $EXIT_CODE