# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import atexit
import socket
import time
import threading
import logging

from rez.utils import json
from rez.utils.logging_ import print_error
from rez.vendor.six.six.moves import queue, urllib
from rez.vendor.pika.adapters.blocking_connection import BlockingConnection
from rez.vendor.pika.connection import ConnectionParameters
from rez.vendor.pika.credentials import PlainCredentials
from rez.vendor.pika.spec import BasicProperties
from rez.config import config


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

    set_pika_log_level()

    conn_kwargs = dict()

    # name the conn like 'rez.publish.{host}'
    conn_kwargs["client_properties"] = {
        "connection_name": "rez.publish.%s" % socket.gethostname()
    }

    host, port = parse_host_and_port(url=host)
    conn_kwargs["host"] = host
    if port is not None:
        conn_kwargs["port"] = port

    if amqp_settings.get("userid"):
        conn_kwargs["credentials"] = PlainCredentials(
            username=amqp_settings.get("userid"),
            password=amqp_settings.get("password")
        )

    params = ConnectionParameters(
        socket_timeout=amqp_settings.get("connect_timeout"),
        **conn_kwargs
    )

    props = BasicProperties(
        content_type="application/json",
        content_encoding="utf-8",
        delivery_mode=amqp_settings.get("message_delivery_mode")
    )

    try:
        conn = BlockingConnection(params)
    except socket.error as e:
        print_error("Cannot connect to the message broker: %s" % e)
        return False

    try:
        channel = conn.channel()

        channel.basic_publish(
            exchange=amqp_settings["exchange_name"],
            routing_key=routing_key,
            body=json.dumps(data),
            properties=props
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


def parse_host_and_port(url):
    _url = urllib.parse.urlsplit(url)
    if not _url.scheme:
        _url = urllib.parse.urlsplit("//" + url)
    host = _url.hostname
    port = _url.port

    return host, port


def set_pika_log_level():
    mod_name = "rez.vendor.pika"

    if config.debug("context_tracking"):
        logging.getLogger(mod_name).setLevel(logging.DEBUG)
    else:
        logging.getLogger(mod_name).setLevel(logging.WARNING)
