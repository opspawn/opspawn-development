#!/bin/bash
# This command tells Dramatiq to look for the broker configuration
# and any defined actors within the 'app.py' file (or module).
# Ensure RabbitMQ is running before executing this.
echo "Starting Dramatiq worker, watching module 'app'..."
dramatiq app