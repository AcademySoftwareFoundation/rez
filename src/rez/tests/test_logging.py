"""
Test importing logging modules.
"""
from rez.tests.util import TestBase
import unittest
from  rez.utils import logging_


class TestLogging(TestBase):

    def test_print(self):
        """Test valid msg and nargs combinations for print_*."""
        for msg in ("Hello", "Hello %s", "Hello %s %s"):
            logging_.print_debug(msg)
            logging_.print_info(msg)
            logging_.print_warning(msg)
            logging_.print_error(msg)
            logging_.print_critical(msg)

            for nargs in ([], ["foo"], ["foo", "bar"]):
                logging_.print_debug(msg, *nargs)
                logging_.print_info(msg, *nargs)
                logging_.print_warning(msg, *nargs)
                logging_.print_error(msg, *nargs)
                logging_.print_critical(msg, *nargs)
