from contextlib import contextmanager
import logging
import time


logger = logging.getLogger(__name__)


def print_debug(msg, *nargs):
    logger.debug(msg % nargs)


def print_info(msg, *nargs):
    logger.info(msg % nargs)


def print_warning(msg, *nargs):
    logger.warning(msg % nargs)


def print_error(msg, *nargs):
    logger.error(msg % nargs)


def print_critical(msg, *nargs):
    logger.critical(msg % nargs)


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


