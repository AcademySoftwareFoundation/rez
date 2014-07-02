import logging.config
import os

__version__ = "2.0.ALPHA.71"
__author__ = "Allan Johns"
__license__ = "LGPL"

module_root_path = __path__[0]

logging.config.fileConfig(os.path.join(module_root_path, 'logging.conf'), disable_existing_loggers=True)
