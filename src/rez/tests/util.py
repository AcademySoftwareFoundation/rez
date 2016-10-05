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
        from rez.util import deep_update

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
    exitcode = None

    # first swap sys.argv...
    old_argv = sys.argv
    new_argv = ['rez-%s' % command] + other_args
    sys.argv = new_argv
    try:

        # then redirect stdout using os.dup2

        # we can't just ye' ol sys.stdout swap trick, because some places may
        # still be holding onto references to the "real" sys.stdout - ie, if
        # a function has a kwarg default (as in rez.status.Status.print_info)
        # So, instead we swap at a file-descriptor level... potentially less
        # portable, but has been tested to work on linux, osx, and windows...
        with tempfile.TemporaryFile(bufsize=0, prefix='rez_cliout') as tf:
            new_fileno = tf.fileno()
            old_fileno = sys.stdout.fileno()
            old_fileno_dupe = os.dup(old_fileno)

            # make sure we flush before any switches...
            sys.stdout.flush()
            # ...then redirect stdout to our temp file...
            os.dup2(new_fileno, old_fileno)
            try:
                try:
                    # and finally invoke the "command-line" rez-COMMAND
                    from rez.cli._main import run
                    run(command)
                except SystemExit as e:
                    exitcode = e.args[0]
            finally:
                # restore stdout
                sys.stdout.flush()
                tf.flush()
                os.dup2(old_fileno_dupe, old_fileno)

            # ok, now read the output we redirected to the file...
            tf.seek(0, os.SEEK_SET)
            output = tf.read()
    finally:
        # restore argv...
        sys.argv = old_argv

    return output, exitcode


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
