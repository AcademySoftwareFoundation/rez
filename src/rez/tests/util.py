import rez.vendor.unittest2 as unittest
from rez.config import config, _create_locked_config
from rez.shells import get_shell_types
from rez.system import system
import tempfile
import shutil
import os.path
import os
import functools


class TestBase(unittest.TestCase):
    """Unit test base class."""
    @classmethod
    def setUpClass(cls):
        cls.settings = {}

    def setUp(self):
        self.maxDiff = None
        # shield unit tests from any user config overrides
        os.environ["REZ_QUIET"] = "true"
        # to make sure config changes from one test don't affect another, copy
        # the overrides dict...
        self._config = _create_locked_config(dict(self.settings))
        config._swap(self._config)

    def tearDown(self):
        config._swap(self._config)
        self._config = None


class TempdirMixin(object):
    """Mixin that adds tmpdir create/delete."""
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="rez_selftest_")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.root):
            shutil.rmtree(cls.root)

def find_file_in_path(to_find, path_str, pathsep=None, reverse=True):
    """Attempts to find the given relative path to_find in the given path
    """
    if pathsep is None:
        pathsep = os.pathsep
    paths = path_str.split(pathsep)
    if reverse:
        paths = reversed(paths)
    for path in paths:
        test_path = os.path.join(path, to_find)
        if os.path.isfile(test_path):
            return test_path
    return None

_CMAKE_EXISTS = None

def cmake_exists():
    """Tests whether cmake is available"""
    global _CMAKE_EXISTS
    if _CMAKE_EXISTS is None:
        import subprocess
        import errno

        with open(os.devnull, 'wb') as DEVNULL:
            try:
                subprocess.check_call(['cmake', '-h'], stdout=DEVNULL,
                                      stderr=DEVNULL)
            except (OSError, IOError, subprocess.CalledProcessError):
                _CMAKE_EXISTS = False
            else:
                _CMAKE_EXISTS = True
    return _CMAKE_EXISTS

def cmake_dependent(fn):
    """Function decorator that skips the test if cmake is not available"""
    if not cmake_exists():
        return unittest.skip('cmake not available')(fn)
    return fn

def shell_dependent(exclude=None):
    """Function decorator that runs the function over all shell types."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            shells = get_shell_types()
            only_shell = os.getenv("__REZ_SELFTEST_SHELL")
            if only_shell:
                shells = [only_shell]

            for shell in shells:
                if exclude and shell in exclude:
                    self.skipTest("This test does not run on %s shell." % shell)
                print "\ntesting in shell: %s..." % shell
                config.override("default_shell", shell)
                func(self, *args, **kwargs)
        return wrapper
    return decorator


def install_dependent(fn):
    """Function decorator that skips tests if not run via 'rez-selftest' tool,
    from a production install"""
    @functools.wraps(fn)
    def _fn(self, *args, **kwargs):
        if os.getenv("__REZ_SELFTEST_RUNNING") and system.is_production_rez_install:
            fn(self, *args, **kwargs)
        else:
            print ("\nskipping test, must be run via 'rez-selftest' tool, from "
                   "a PRODUCTION rez installation.")
    return _fn


# Copyright 2016 Allan Johns.
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
