from rez.utils._version import _rez_version
import logging.config
import os


__version__ = _rez_version
__author__ = "Allan Johns"
__license__ = "LGPL"

module_root_path = __path__[0]

logging_conf_file = os.environ.get(
    'REZ_LOGGING_CONF',
    os.path.join(module_root_path, 'utils', 'logging.conf'))
logging.config.fileConfig(logging_conf_file, disable_existing_loggers=False)
