__version__ = '1.2.0'

import logging

# Add NullHandler before importing Pika modules to prevent logging warnings
logging.getLogger(__name__).addHandler(logging.NullHandler())
