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


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
