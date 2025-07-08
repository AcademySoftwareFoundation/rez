# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import unittest
from rez import module_root_path
from rez.config import config, _create_locked_config
from rez.shells import get_shell_types, get_shell_class
from rez.system import system
import tempfile
import threading
import time
import shutil
import os.path
import os
import functools
import sys
import json
import copy
from contextlib import contextmanager

# https://pypi.org/project/parameterized
try:
    from parameterized import parameterized
    use_parameterized = True
except ImportError:
    use_parameterized = False


class TestBase(unittest.TestCase):
    """Unit test base class."""
    def __init__(self, *nargs, **kwargs):
        super(TestBase, self).__init__(*nargs, **kwargs)
        self.setup_once_called = False

    @classmethod
    def setUpClass(cls):
        cls.settings = {}

    def setUp(self):
        # We have some tests that unfortunately don't clean themselves up
        # after they are done. Store the origianl environment to be
        # restored in tearDown
        self.__environ = copy.deepcopy(os.environ)

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
        os.environ = self.__environ
        # Try to clear as much caches as possible to avoid tests
        # leaking data into each other.
        system.clear_caches()

    @classmethod
    def data_path(cls, *dirs):
        """Get path to test data.
        """
        path = os.path.join(module_root_path, "data", "tests", *dirs)
        return os.path.realpath(path)

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

    def get_settings_env(self):
        """Get an environ dict that applies the current settings.

        This is required for cases where a subproc has to pick up the same
        config settings that the test case has set.
        """
        return dict(
            ("REZ_%s_JSON" % k.upper(), json.dumps(v))
            for k, v in self.settings.items()
        )

    def inject_python_repo(self):
        self.update_settings(
            {
                "packages_path": config.packages_path + [os.environ["__REZ_SELFTEST_PYTHON_REPO"]],
            }
        )


class TempdirMixin(object):
    """Mixin that adds tmpdir create/delete."""
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="rez_selftest_")

    @classmethod
    def tearDownClass(cls):
        if os.getenv("REZ_KEEP_TMPDIRS"):
            print("Tempdir kept due to $REZ_KEEP_TMPDIRS: %s" % cls.root)
            return

        # The retries are here because there is at least one case in the
        # tests where a subproc can be writing to files in a tmpdir after
        # the tests are completed (this is the rez-pkg-cache proc in the
        # test_package_cache:test_caching_on_resolve test).
        #
        retries = 5

        if os.path.exists(cls.root):
            for i in range(retries):
                try:
                    shutil.rmtree(cls.root)
                    break
                except:
                    if i < (retries - 1):
                        time.sleep(0.2)


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
    names = [program_name] + list(program_names)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not all(shutil.which(x) for x in names):
                self.skipTest(
                    "Requires all programs to be present and functioning: %s"
                    % names
                )

            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def get_available_shells():
    """Helper to get all available shells in a testing context."""
    shells = get_shell_types()

    only_shell = os.getenv("__REZ_SELFTEST_SHELL")
    if only_shell:
        shells = [only_shell]

    # filter to only those shells available
    return [
        x for x in shells
        if get_shell_class(x).is_available()
    ]


def per_available_shell(exclude=None):
    """Function decorator that runs the function over all available shell types.
    """
    exclude = exclude or []

    shells = get_shell_types()

    only_shell = os.getenv("__REZ_SELFTEST_SHELL")
    if only_shell:
        shells = [only_shell]

    # filter to only those shells available
    shells = [
        x for x in shells
        if get_shell_class(x).is_available()
        and x not in (exclude or [])
    ]

    # https://pypi.org/project/parameterized
    if use_parameterized:

        class rez_parametrized(parameterized):

            # Taken from https://github.com/wolever/parameterized/blob/b9f6a640452bcfdea08efc4badfe5bfad043f099/parameterized/parameterized.py#L612  # noqa
            @classmethod
            def param_as_standalone_func(cls, p, func, name):
                # @wraps(func)
                def standalone_func(*args, **kwargs):
                    # Make sure to set the default shell to the requested shell. This
                    # simplifies tests and removes the need to remember passing the shell
                    # kward to execute_shell and co inside the tests.
                    # Subclassing parameterized is fragile, but we can't do better for now.
                    args[0].update_settings({"default_shell": p.args[0]})
                    return func(*(args + p.args), **p.kwargs, **kwargs)

                standalone_func.__name__ = name

                # place_as is used by py.test to determine what source file should be
                # used for this test.
                standalone_func.place_as = func

                # Remove __wrapped__ because py.test will try to look at __wrapped__
                # to determine which parameters should be used with this test case,
                # and obviously we don't need it to do any parameterization.
                try:
                    del standalone_func.__wrapped__
                except AttributeError:
                    pass
                return standalone_func

        return rez_parametrized.expand(shells)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, shell=None):

            for shell in shells:
                print("\ntesting in shell: %s..." % shell)

                try:
                    # Make sure to set the default shell to the requested shell. This
                    # simplifies tests and removes the need to remember passing the shell
                    # kward to execute_shell and co inside the tests.
                    self.update_settings({"default_shell": shell})

                    func(self, shell=shell)
                except Exception as e:
                    # Add the shell to the exception message, if possible.
                    # In some IDEs the args do not exist at all.
                    if hasattr(e, "args") and e.args:
                        try:
                            args = list(e.args)
                            args[0] = str(args[0]) + " (in shell '{}')".format(shell)
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
                    "https://rez.readthedocs.io/en/stable/installation.html#installation-script"
                )
        return wrapper
    return decorator


_restore_sys_path_lock = threading.Lock()
_restore_os_environ_lock = threading.Lock()


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
    with _restore_sys_path_lock:
        original = sys.path[:]

        yield sys.path

        del sys.path[:]
        sys.path.extend(original)


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
    with _restore_os_environ_lock:
        original = os.environ.copy()

        yield os.environ

        os.environ.clear()
        os.environ.update(original)
