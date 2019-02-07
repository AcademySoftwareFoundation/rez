from rez.utils._version import _rez_version
import logging.config
import atexit
import os


__version__ = _rez_version
__author__ = "Allan Johns"
__license__ = "LGPL"


module_root_path = __path__[0]


logging_conf_file = os.environ.get(
    'REZ_LOGGING_CONF',
    os.path.join(module_root_path, 'utils', 'logging.conf'))
logging.config.fileConfig(logging_conf_file, disable_existing_loggers=False)


# actions registered on SIGUSR1
action = os.getenv("REZ_SIGUSR1_ACTION")
if action:
    import signal, traceback

    if action == "print_stack":
        def callback(sig, frame):
            txt = ''.join(traceback.format_stack(frame))
            print
            print txt
    else:
        callback = None

    if callback:
        signal.signal(signal.SIGUSR1, callback)  # Register handler


