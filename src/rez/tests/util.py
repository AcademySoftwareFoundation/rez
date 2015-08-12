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
        os.environ["REZ_QUIET"] = "true"

        # shield unit tests from any user config overrides
        self.setup_config()

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
        self.teardown_config()

        # ...then copy the class settings dict to instance, so we can
        # modify...
        if override:
            self.settings = dict(new_settings)
        else:
            self.settings = dict(type(self).settings)
            self.settings.update(new_settings)

        # now swap the config back in...
        self.setup_config()


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
            for shell in get_shell_types():
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

def get_cli_output(args):
    """Invoke the named command-line rez command, with the given string
    command line args

    Note that it does this by calling rez.cli._main.run within the same
    python process, for efficiency; if for some reason this is not sufficient
    encapsulation / etc, you can use subprocess to invoke the rez as a
    separate process

    Returns
    -------
    stdout : basestring
        the captured output to sys.stdout
    exitcode : int
        the returncode from the command
    """

    import sys
    from StringIO import StringIO

    command = args[0]
    other_args = list(args[1:])
    if command.startswith('rez-'):
        command = command[4:]

    # swap out sys.stdout, so we can capture it...
    old_stdout = sys.stdout
    captured_stdout = StringIO()
    sys.stdout = captured_stdout

    exitcode = None
    try:
        # ...and swap out argv...
        old_argv = sys.argv
        new_argv = ['rez-%s' % command] + other_args
        sys.argv = new_argv
        try:
            try:
                # and finally invoke the "command-line" rez-COMMAND
                from rez.cli._main import run
                run(command)
            except SystemExit as e:
                exitcode = e.args[0]
        finally:
            sys.argv = old_argv
    finally:
        sys.stdout = old_stdout

    return captured_stdout.getvalue(), exitcode
