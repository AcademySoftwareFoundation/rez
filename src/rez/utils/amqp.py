import socket
import threading
from Queue import Queue

from rez.utils import json
from rez.utils.logging_ import print_error
from rez.vendor.amqp import Connection, basic_message


_lock = threading.Lock()
_queue = Queue()
_thread = None


def publish_message(host, amqp_settings, routing_key, data, async=False):
    """Publish an AMQP message.

    Returns:
        bool: True if message was sent successfully.
    """
    global _thread

    kwargs = {
        "host": host,
        "amqp_settings": amqp_settings,
        "routing_key": routing_key,
        "data": data
    }

    if not async:
        return _publish_message(**kwargs)

    if _thread is None:
        with _lock:
            if _thread is None:
                _thread = threading.Thread(target=_publish_messages_async)
                _thread.daemon = True
                _thread.start()

    _queue.put(kwargs)
    return True


def _publish_message(host, amqp_settings, routing_key, data):
    """Publish an AMQP message.

    Returns:
        bool: True if message was sent successfully.
    """
    if host == "stdout":
        print("Published to %s: %s" % (routing_key, data))
        return True

    try:
        conn = Connection(
            host=host,
            port=amqp_settings["port"],
            userid=amqp_settings["userid"],
            password=amqp_settings["password"],
            connect_timeout=amqp_settings["connect_timeout"]
        )
    except socket.error as e:
        print_error("Cannot connect to the message broker: %s" % (e))
        return False

    channel = conn.channel()

    # Declare the exchange
    try:
        channel.exchange_declare(
            amqp_settings["exchange_name"],
            amqp_settings["exchange_type"],
            durable=amqp_settings["exchange_durable"],
            auto_delete=amqp_settings["exchange_auto_delete"]
        )
    except Exception as e:
        print_error("Failed to declare an exchange: %s" % (e))
        return False

    # build the message
    msg = basic_message.Message(
        body=json.dumps(data),
        delivery_mode=amqp_settings["message_delivery_mode"],
        content_type="application/json",
        content_encoding="utf-8"
    )

    # publish the message
    try:
        channel.basic_publish(
            msg,
            amqp_settings["exchange_name"],
            routing_key
        )
    except Exception as e:
        print_error("Failed to publish message: %s" % (e))
        return False

    return True


def _publish_messages_async():
    while True:
        kwargs = _queue.get()
        _publish_message(**kwargs)
