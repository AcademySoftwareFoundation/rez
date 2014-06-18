import rez.vendor.unittest2 as unittest
from rez.settings import settings
from rez.shells import get_shell_types
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
        """Shield unit tests from any settings overrides."""
        settings.lock()
        for k,v in self.settings.iteritems():
            settings.set(k, v)

    def tearDown(self):
        settings.lock(False)


class TempdirMixin(object):
    """Mixin that adds tmpdir create/delete."""
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="rez_test_")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.root):
            shutil.rmtree(cls.root)


def shell_dependent(fn):
    """Function decorator that runs the function over all shell types."""
    def _fn(self, *args, **kwargs):
        for shell in get_shell_types():
            print "\ntesting in shell: %s..." % shell
            settings.set("default_shell", shell)
            fn(self, *args, **kwargs)
    return _fn


def install_dependent(fn):
    """Function decorator that skips tests if not run via 'rez-cli' tool."""
    def _fn(self, *args, **kwargs):
        if os.getenv("__REZ_TEST_RUNNING"):
            fn(self, *args, **kwargs)
        else:
            print "\nskipping test, must be run via 'rez-test' tool"
    return _fn
