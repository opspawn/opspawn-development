#!/bin/bash
# Sets the Flask application file and runs the development server.
# Ensure RabbitMQ is running before executing this.
echo "Starting Flask API server on port 5001..."
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5001