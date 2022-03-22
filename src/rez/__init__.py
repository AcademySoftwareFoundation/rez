# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import print_function

from rez.utils._version import _rez_version
import sys
import os


__version__ = _rez_version
__author__ = "Allan Johns"
__license__ = "LGPL"


module_root_path = __path__[0]  # noqa


# TODO: Revamp logging. For now, this is here for backwards compatibility
def _init_logging():
    logging_conf = os.getenv("REZ_LOGGING_CONF")
    if logging_conf:
        import logging.config
        logging.config.fileConfig(logging_conf, disable_existing_loggers=False)
        return

    import logging
    from rez.utils.colorize import ColorizedStreamHandler

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%X"
    )
    handler = ColorizedStreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    logger = logging.getLogger("rez")
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)


_init_logging()


# actions registered on SIGUSR1
action = os.getenv("REZ_SIGUSR1_ACTION")
if action:
    import signal
    import traceback

    if action == "print_stack":
        def callback(sig, frame):
            txt = ''.join(traceback.format_stack(frame))
            print()
            print(txt)
    else:
        callback = None

    if callback:
        signal.signal(signal.SIGUSR1, callback)  # Register handler
