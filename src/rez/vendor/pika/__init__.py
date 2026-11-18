__version__ = '1.5.0'

import logging

# Add NullHandler before importing Pika modules to prevent logging warnings
logging.getLogger(__name__).addHandler(logging.NullHandler())

# ruff: noqa: E402

from rez.vendor.pika import adapters, frame, spec
from rez.vendor.pika.adapters import BaseConnection, BlockingConnection, Connection, SelectConnection
from rez.vendor.pika.adapters.utils.connection_workflow import AMQPConnectionWorkflow
from rez.vendor.pika.connection import ConnectionParameters, SSLOptions, URLParameters
from rez.vendor.pika.credentials import PlainCredentials
from rez.vendor.pika.delivery_mode import DeliveryMode
from rez.vendor.pika.spec import BasicProperties

__all__ = [
    'AMQPConnectionWorkflow',
    'BaseConnection',
    'BasicProperties',
    'BlockingConnection',
    'Connection',
    'ConnectionParameters',
    'DeliveryMode',
    'PlainCredentials',
    'SSLOptions',
    'SelectConnection',
    'URLParameters',
    'adapters',
    'frame',
    'spec',
]
