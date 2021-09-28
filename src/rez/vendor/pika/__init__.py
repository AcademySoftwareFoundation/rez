__version__ = '1.2.0'

import logging

# Add NullHandler before importing Pika modules to prevent logging warnings
logging.getLogger(__name__).addHandler(logging.NullHandler())

# pylint: disable=C0413

from rez.vendor.pika.connection import ConnectionParameters
from rez.vendor.pika.connection import URLParameters
from rez.vendor.pika.connection import SSLOptions
from rez.vendor.pika.credentials import PlainCredentials
from rez.vendor.pika.spec import BasicProperties
from rez.vendor.pika.delivery_mode import DeliveryMode

from rez.vendor.pika import adapters
from rez.vendor.pika.adapters import BaseConnection
from rez.vendor.pika.adapters import BlockingConnection
from rez.vendor.pika.adapters import SelectConnection

from rez.vendor.pika.adapters.utils.connection_workflow import AMQPConnectionWorkflow
