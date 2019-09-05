import atexit
import socket
import time
import threading

from rez.utils import json
from rez.utils.data_utils import remove_nones
from rez.utils.logging_ import print_error
from rez.vendor.amqp import Connection, basic_message
from rez.vendor.six.six.moves import queue


_lock = threading.Lock()
_queue = queue.Queue()
_thread = None
_num_pending = 0


def publish_message(host, amqp_settings, routing_key, data, block=True):
    """Publish an AMQP message.

    Returns:
        bool: True if message was sent successfully.
    """
    global _thread
    global _num_pending

    kwargs = {
        "host": host,
        "amqp_settings": amqp_settings,
        "routing_key": routing_key,
        "data": data
    }

    if block:
        return _publish_message(**kwargs)

    if _thread is None:
        with _lock:
            if _thread is None:
                _thread = threading.Thread(target=_publish_messages_async)
                _thread.daemon = True
                _thread.start()

    with _lock:
        _num_pending += 1

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
        conn = Connection(**remove_nones(
            host=host,
            userid=amqp_settings.get("userid"),
            password=amqp_settings.get("password"),
            connect_timeout=amqp_settings.get("connect_timeout")
        ))
    except socket.error as e:
        print_error("Cannot connect to the message broker: %s" % (e))
        return False

    channel = conn.channel()

    # build the message
    msg = basic_message.Message(**remove_nones(
        body=json.dumps(data),
        delivery_mode=amqp_settings.get("message_delivery_mode"),
        content_type="application/json",
        content_encoding="utf-8"
    ))

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
    finally:
        conn.close()

    return True


def _publish_messages_async():
    global _num_pending

    while True:
        kwargs = _queue.get()

        try:
            _publish_message(**kwargs)
        finally:
            with _lock:
                _num_pending -= 1


@atexit.register
def on_exit():
    # Give pending messages a chance to publish, otherwise a command like
    # 'rez-env --output ...' could exit before the publish.
    #
    t = time.time()
    maxtime = 5
    timeinc = 0.1

    while _num_pending and (time.time() - t) < maxtime:
        time.sleep(timeinc)
