import logging
import logging.config
import os
from rez import module_root_path


logger = logging.getLogger(__name__)


def setup_logging():
    logging_conf_file = os.environ.get('REZ_LOGGING_CONF',
                                       os.path.join(module_root_path, 'utils', 'logging.conf'))
    logging.config.fileConfig(logging_conf_file, disable_existing_loggers=False)


def print_debug(msg):
    logger.debug(msg)


def print_warning(msg):
    logger.warning(msg)


def print_error(msg):
    logger.error(msg)


def print_critical(msg):
    logger.critical(msg)


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
