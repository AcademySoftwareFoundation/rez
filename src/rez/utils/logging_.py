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
from contextlib import contextmanager
import logging
import time
import sys
import os


logger = logging.getLogger(__name__)


def print_debug(msg, *nargs):
    logger.debug(msg, *nargs)


def print_info(msg, *nargs):
    logger.info(msg, *nargs)


def print_warning(msg, *nargs):
    logger.warning(msg, *nargs)


def print_error(msg, *nargs):
    logger.error(msg, *nargs)


def print_critical(msg, *nargs):
    logger.critical(msg, *nargs)


def get_debug_printer(enabled=True):
    return _Printer(enabled, logger.debug)


def get_info_printer(enabled=True):
    return _Printer(enabled, logger.info)


def get_warning_printer(enabled=True):
    return _Printer(enabled, logger.warning)


def get_error_printer(enabled=True):
    return _Printer(enabled, logger.error)


def get_critical_printer(enabled=True):
    return _Printer(enabled, logger.critical)


class _Printer(object):
    def __init__(self, enabled=True, printer_function=None):
        self.printer_function = printer_function if enabled else None

    def __call__(self, msg, *nargs):
        if self.printer_function:
            if nargs:
                msg = msg % nargs
            self.printer_function(msg)

    def __nonzero__(self):
        return bool(self.printer_function)

    __bool__ = __nonzero__  # py3 compat


@contextmanager
def log_duration(printer, msg):
    t1 = time.time()
    yield None

    t2 = time.time()
    secs = t2 - t1
    printer(msg, str(secs))


def view_file_logs(globbed_path, loglevel_index=None):
    """View logs from one or more logfiles.

    Prints to stdout.

    Args:
        globbed_path (str): Logfiles, eg '/foo/logs/*.log'
        loglevel_index (int): Position on each log line where log level
            (INFO etc) is expected. This is used for colorisation only, and if
            None, no colors are applied.
    """
    from rez.utils import colorize
    import glob

    colors = {
        "DEBUG": colorize.debug,
        "INFO": colorize.info,
        "WARNING": colorize.warning,
        "ERROR": colorize.error
    }

    filepaths = glob.glob(globbed_path)
    if not filepaths:
        print("No logs.", file=sys.stderr)

    # sort logfiles by ctime
    filepaths = sorted(filepaths, key=lambda x: os.stat(x).st_ctime)

    last_color = None

    for filepath in filepaths:
        with open(filepath) as f:
            while True:
                line = f.readline()
                if not line:
                    break

                line = line.rstrip()  # strip newline
                color = last_color

                if loglevel_index:
                    parts = line.split()
                    if len(parts) > loglevel_index:
                        color = colors.get(parts[loglevel_index], last_color)
                        last_color = color

                if color:
                    colorize.Printer()(line, color)
                else:
                    print(line)
