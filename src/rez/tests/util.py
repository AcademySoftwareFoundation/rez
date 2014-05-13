import rez.contrib.unittest2 as unittest
from rez.settings import settings
from rez.shells import create_shell
import tempfile
import shutil
import os.path



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


class ShellDependentTest(TestBase):
    """Base class for tests that are sensitive to shell type."""
    def __init__(self, fn, shell=None):
        TestBase.__init__(self, fn)
        self.shell = shell

    def setUp(self):
        TestBase.setUp(self)
        settings.set("default_shell", self.shell)

    def create_shell(self):
        return create_shell(self.shell)

    def test_create_shell(self):
        print "\n\nSHELL TYPE: %s" % self.shell
        self.create_shell()


class TempdirMixin(object):
    """Mixin that adds tmpdir create/delete."""
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="rez_test_")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.root):
            shutil.rmtree(cls.root)
