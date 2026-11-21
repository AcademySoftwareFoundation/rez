# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import atexit
import json
import socket
import ssl
import time
import threading
import logging
import urllib.parse
import queue

from rez.utils.logging_ import print_debug, print_error, print_warning
from rez.vendor.pika.adapters.blocking_connection import BlockingConnection
from rez.vendor.pika.connection import ConnectionParameters, SSLOptions
from rez.vendor.pika.credentials import PlainCredentials
from rez.vendor.pika.exceptions import AMQPConnectionError
from rez.vendor.pika.spec import BasicProperties
from rez.config import config


_lock = threading.Lock()
_queue = queue.Queue()
_thread = None
_num_pending = 0


def publish_message(host, amqp_settings, routing_key, data, block: bool = True):
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


def _publish_message(host, amqp_settings, routing_key, data) -> bool:
    """Publish an AMQP message.

    Returns:
        bool: True if message was sent successfully.
    """
    if host == "stdout":
        print("Published to %s: %s" % (routing_key, data))
        return True

    if config.debug("context_tracking"):
        set_pika_log_level()

    conn_kwargs = dict()

    # name the conn like 'rez.publish.{host}'
    conn_kwargs["client_properties"] = {
        "connection_name": "rez.publish.%s" % socket.gethostname()
    }

    original_host = host
    host, port = parse_host_and_port(url=host)
    conn_kwargs["host"] = host
    if port is not None:
        conn_kwargs["port"] = port

    if amqp_settings.get("userid"):
        conn_kwargs["credentials"] = PlainCredentials(
            username=amqp_settings.get("userid"),
            password=amqp_settings.get("password")
        )

    props = BasicProperties(
        content_type="application/json",
        content_encoding="utf-8",
        delivery_mode=amqp_settings.get("message_delivery_mode")
    )

    try:
        if original_host.startswith("amqps://"):
            conn_kwargs["ssl_options"] = _create_ssl_options(host, amqp_settings)

        params = ConnectionParameters(
            socket_timeout=amqp_settings.get("connect_timeout"),
            **conn_kwargs
        )
        conn = BlockingConnection(params)
    except (socket.error, AMQPConnectionError) as e:
        if original_host:
            # Host was explicitly passed in. This is an unexpected failure.
            print_warning("Cannot connect to the message broker: %s" % e)
        elif config.debug("context_tracking"):
            # No host configured, only display this in debug.
            print_debug("Cannot connect to the message broker: %s" % e)
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


def _publish_messages_async() -> None:
    global _num_pending

    while True:
        kwargs = _queue.get()

        try:
            _publish_message(**kwargs)
        finally:
            with _lock:
                _num_pending -= 1


@atexit.register
def on_exit() -> None:
    # Give pending messages a chance to publish, otherwise a command like
    # 'rez-env --output ...' could exit before the publish.
    #
    t = time.time()
    maxtime = 5
    timeinc = 0.1

    while _num_pending and (time.time() - t) < maxtime:
        time.sleep(timeinc)


def _create_ssl_options(host, amqp_settings) -> SSLOptions:
    """Create TLS options that verify the broker's certificate and hostname.

    Only ``ssl_ca_file`` is trusted if set; otherwise see _create_default_ssl_context.
    ``ssl_cert_file`` (and ``ssl_key_file``, if the key is not in the cert file)
    enable mutual TLS.
    """
    ca_file = amqp_settings.get("ssl_ca_file")
    if ca_file:
        context = ssl.create_default_context(cafile=ca_file)
    else:
        context = _create_default_ssl_context()

    if amqp_settings.get("ssl_cert_file"):
        context.load_cert_chain(
            amqp_settings["ssl_cert_file"],
            keyfile=amqp_settings.get("ssl_key_file") or None
        )
    return SSLOptions(context, server_hostname=host)


def _create_default_ssl_context() -> ssl.SSLContext:
    """Create a TLS context that trusts the system's CAs.

    Python alone only reads OpenSSL's default CA locations, which is the system
    trust store on Linux but not the Keychain on macOS. Neither package below is
    a rez dependency; each is used if it is installed:

    - truststore (Python 3.10+) verifies with the OS itself (Keychain on macOS,
      the certificate store on Windows).
    - certifi's CA bundle is added to Python's defaults, which on python.org
      macOS builds are empty.
    """
    try:
        import truststore
    except ImportError:
        pass
    else:
        if config.debug("context_tracking"):
            print_debug("Using truststore to configure the AMQP TLS client")
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    context = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        pass
    else:
        if config.debug("context_tracking"):
            print_debug("Using certifi to configure the AMQP TLS client: %s" % certifi.where())
        context.load_verify_locations(cafile=certifi.where())
        return context

    if config.debug("context_tracking"):
        print_debug(
            "truststore and certifi are not installed, falling back to Python's "
            "default way of loading CAs to connect to the AMQP broker"
        )
    return context


def parse_host_and_port(url):
    # Prepend // unless the URL already has a scheme (e.g. "amqp://").
    # A bare "host:port" string causes urlsplit to misparse the hostname.
    if "://" not in url and not url.startswith("//"):
        url = "//" + url
    _url = urllib.parse.urlsplit(url)
    host = _url.hostname
    port = _url.port

    return host, port


def set_pika_log_level() -> None:
    mod_name = "rez.vendor.pika"

    if config.debug("context_tracking"):
        logging.getLogger(mod_name).setLevel(logging.DEBUG)
