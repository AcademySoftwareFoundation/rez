from contextlib import contextmanager
import logging
import logging.config
import os
import time
from rez import module_root_path


logger = logging.getLogger(__name__)


def setup_logging():
    fname = os.path.join(module_root_path, 'utils', 'logging.conf')
    logging_conf_file = os.environ.get('REZ_LOGGING_CONF', fname)
    logging.config.fileConfig(
        logging_conf_file, disable_existing_loggers=False)


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


@contextmanager
def log_duration(printer, msg):
    t1 = time.time()
    yield None

    t2 = time.time()
    secs = t2 - t1
    printer(msg, str(secs))


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
