"""Enables unit testing from root directory of source."""
import sys
import os.path
import inspect


_test_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
sys.path.insert(0, os.path.join(_test_dir, '..', 'src'))

from rez.tests.test_build import TestBuild
from rez.tests.test_commands import TestCommands
from rez.tests.test_context import TestContext
from rez.tests.test_formatter import TestFormatter
from rez.tests.test_rex import TestRex
from rez.tests.test_shells import TestShells
from rez.tests.test_solver import TestSolver
from rez.tests.test_resources import TestResources
from rez.tests.test_packages import TestPackages
