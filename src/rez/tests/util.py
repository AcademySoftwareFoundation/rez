from __future__ import print_function

import unittest
from rez.config import config, _create_locked_config
from rez.shells import get_shell_types, get_shell_class
from rez.system import system
import tempfile
import shutil
import os.path
import os
import functools
import sys
from contextlib import contextmanager


class TestBase(unittest.TestCase):
    """Unit test base class."""
    def __init__(self, *nargs, **kwargs):
        super(TestBase, self).__init__(*nargs, **kwargs)
        self.setup_once_called = False

    @classmethod
    def setUpClass(cls):
        cls.settings = {}

    def setUp(self):
        self.maxDiff = None
        os.environ["REZ_QUIET"] = "true"

        # shield unit tests from any user config overrides
        self.setup_config()

        # hook to run code once before all tests, but after the config has
        # been overridden.
        if not self.setup_once_called:
            self.setup_once()
            self.setup_once_called = True

    def setup_once(self):
        pass

    def tearDown(self):
        self.teardown_config()

    # These are moved into their own functions so update_settings can call
    # them without having to call setUp / tearDown, and without worrying
    # about future or subclass modifications to those methods...
    def setup_config(self):
        # to make sure config changes from one test don't affect another, copy
        # the overrides dict...
        self._config = _create_locked_config(dict(self.settings))
        config._swap(self._config)

    def teardown_config(self):
        # moved to it's own section because it's called in update_settings...
        # so if in the future, tearDown does more than call this,
        # update_settings is still valid
        config._swap(self._config)
        self._config = None

    def update_settings(self, new_settings, override=False):
        """Can be called within test methods to modify settings on a
        per-test basis (as opposed cls.settings, which modifies it for all
        tests on the class)

        Note that multiple calls will not "accumulate" updates, but will
        instead patch the class's settings with the new_settings each time.

        new_settings : dict
            the updated settings to override the config with
        override : bool
            normally, the resulting config will be the result of merging
            the base cls.settings with the new_settings - ie, like doing
            cls.settings.update(new_settings).  If this is True, however,
            then the cls.settings will be ignored entirely, and the
            new_settings will be the only configuration settings applied
        """
        # restore the "normal" config...
        from rez.utils.data_utils import deep_update

        self.teardown_config()

        # ...then copy the class settings dict to instance, so we can
        # modify...
        if override:
            self.settings = dict(new_settings)
        else:
            self.settings = dict(type(self).settings)
            deep_update(self.settings, new_settings)

        # now swap the config back in...
        self.setup_config()


class TempdirMixin(object):
    """Mixin that adds tmpdir create/delete."""
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="rez_selftest_")

    @classmethod
    def tearDownClass(cls):
        if not os.getenv("REZ_KEEP_TMPDIRS"):
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


def program_dependent(program_name, *program_names):
    """Function decorator that skips the function if not all given programs are
    visible."""
    import subprocess

    program_tests = {
        "cmake": ['cmake', '-h'],
        "make": ['make', '-h'],
        "g++": ["g++", "--help"]
    }

    # test if programs all exist
    def _test(name):
        command = program_tests[name]

        with open(os.devnull, 'wb') as DEVNULL:
            try:
                subprocess.check_call(command, stdout=DEVNULL, stderr=DEVNULL)
            except (OSError, IOError, subprocess.CalledProcessError):
                return False
            else:
                return True

    names = [program_name] + list(program_names)
    all_exist = all(_test(x) for x in names)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not all_exist:
                self.skipTest(
                    "Requires all programs to be present and functioning: %s"
                    % names
                )

            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def per_available_shell():
    """Function decorator that runs the function over all available shell types."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            shells = get_shell_types()

            only_shell = os.getenv("__REZ_SELFTEST_SHELL")
            if only_shell:
                shells = [only_shell]

            # filter to only those shells available
            shells = [
                x for x in shells
                if get_shell_class(x).is_available()
            ]

            for shell in shells:
                print("\ntesting in shell: %s..." % shell)
                config.override("default_shell", shell)

                try:
                    func(self, *args, **kwargs)
                except Exception as e:
                    # Add the shell to the exception message, if possible.
                    # In some IDEs the args do not exist at all.
                    if hasattr(e, "args") and e.args:
                        try:
                            args = list(e.args)
                            args[0] += " (in shell '{}')".format(shell)
                            e.args = tuple(args)
                        except:
                            raise e
                    raise
        return wrapper
    return decorator


def install_dependent():
    """Function decorator that skips tests if not run via 'rez-selftest' tool,
    from a production install"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if os.getenv("__REZ_SELFTEST_RUNNING") and system.is_production_rez_install:
                return func(self, *args, **kwargs)
            else:
                self.skipTest(
                    "Must be run via 'rez-selftest' tool, see "
                    "https://github.com/nerdvegas/rez/wiki/Installation#installation-script"
                )
        return wrapper
    return decorator


@contextmanager
def restore_sys_path():
    """Encapsulate changes to sys.path and return to the original state.

    This context manager lets you wrap modifications of sys.path and not worry
    about reverting back to the original.

    Examples:
        >>> path = '/arbitrary/path'
        >>> with sys_path():
        >>>     sys.path.insert(0, '/arbitrary/path')
        >>>     assert path in sys.path
        True

        >>> assert path in sys.path
        False

    Yields:
        list: The original sys.path.
    """
    original = sys.path[:]
    yield sys.path
    sys.path = original


@contextmanager
def restore_os_environ():
    """Encapsulate changes to os.environ and return to the original state.

    This context manager lets you wrap modifications of os.environ and not
    worry about reverting back to the original.

    Examples:
        >>> key = 'ARBITRARY_KEY'
        >>> value = 'arbitrary_value'
        >>> with os_environ():
        >>>     os.environ[key] = value
        >>>     assert key in os.environ
        True

        >>> assert key in os.environ
        False

    Yields:
        dict: The original os.environ.
    """
    original = os.environ.copy()
    yield os.environ
    os.environ = original


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
