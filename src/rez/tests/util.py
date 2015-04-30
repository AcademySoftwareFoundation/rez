import rez.vendor.unittest2 as unittest
from rez.config import config, _create_locked_config
from rez.shells import get_shell_types
from rez.system import system
import tempfile
import shutil
import os.path
import os


class TestBase(unittest.TestCase):
    """Unit test base class."""
    @classmethod
    def setUpClass(cls):
        cls.settings = {}

    def setUp(self):
        self.maxDiff = None
        # shield unit tests from any user config overrides
        os.environ["REZ_QUIET"] = "true"
        self._config = _create_locked_config(self.settings)
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


def shell_dependent(exclude=None):
    """Function decorator that runs the function over all shell types."""
    def decorator(func):
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
    def _fn(self, *args, **kwargs):
        if os.getenv("__REZ_SELFTEST_RUNNING") and system.is_production_rez_install:
            fn(self, *args, **kwargs)
        else:
            print ("\nskipping test, must be run via 'rez-selftest' tool, from "
                   "a PRODUCTION rez installation.")
    return _fn
