import time
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from flask import Flask, jsonify

# 1. Configure Dramatiq Broker
# Using default guest user on localhost, assuming standard RabbitMQ setup
# No specific vhost needed for this minimal example
broker_url = "amqp://guest:guest@localhost:5672/"
rabbitmq_broker = RabbitmqBroker(url=broker_url)
dramatiq.set_broker(rabbitmq_broker)

# 2. Define Dramatiq Actor (after setting the broker)
@dramatiq.actor
def simple_task(value: int):
    """
    A simple task that prints messages and sleeps.
    """
    print(f"WORKER: Received task with value: {value}")
    print(f"WORKER: Sleeping for {value} seconds...")
    time.sleep(value)
    print(f"WORKER: Finished task for value: {value}")
    # Actors don't typically return values that are directly used by the caller
    # unless using result backends, which we are skipping for simplicity.

# 3. Create Flask App
app = Flask(__name__)

# 4. Define Flask Route to Submit Task
@app.route('/submit/<int:value>', methods=['POST'])
def submit_task(value: int):
    """
    API endpoint to submit the simple_task to the queue.
    """
    print(f"API: Received request to submit task with value: {value}")
    # Send the task to the queue
    message = simple_task.send(value)
    print(f"API: Task sent with message ID: {message.message_id}")
    return jsonify({
        "status": "submitted",
        "value": value,
        "message_id": message.message_id
    }), 202 # Accepted

# Optional: Add a root route for basic check
@app.route('/', methods=['GET'])
def index():
    return "Flask-Dramatiq Test API is running!"

if __name__ == '__main__':
    # This is typically not used when running with Flask CLI or Gunicorn,
    # but can be useful for direct script execution testing (without hot-reload).
    app.run(host='0.0.0.0', port=5001, debug=True)