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
