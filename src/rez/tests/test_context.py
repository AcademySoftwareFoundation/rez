from rez.tests.util import TestBase, TempdirMixin
from rez.resolved_context import ResolvedContext
from rez.bind import hello_world
import rez.vendor.unittest2 as unittest
import subprocess
import os.path
import os


class TestContext(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        packages_path = os.path.join(cls.root, "packages")
        os.makedirs(packages_path)
        hello_world.bind(packages_path)

        cls.settings = dict(
            packages_path=[packages_path],
            implicit_packages=[],
            add_bootstrap_path=False,
            warn_untimestamped=False,
            resolve_caching=False)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_create_context(self):
        """Test creation of context."""
        r = ResolvedContext([])
        r.print_info()

        r = ResolvedContext(["hello_world"])
        r.print_info()

    def test_execute_command(self):
        """Test command execution in context."""
        r = ResolvedContext(["hello_world"])
        p = r.execute_command(["hello_world"], stdout=subprocess.PIPE)
        stdout, _ = p.communicate()
        stdout = stdout.strip()
        self.assertEqual(stdout, "Hello Rez World!")

    def test_serialize(self):
        """Test save/load of context."""
        # save
        file = os.path.join(self.root, "test.rxt")
        r = ResolvedContext(["hello_world"])
        r.save(file)
        # load
        r2 = ResolvedContext.load(file)
        self.assertEqual(r.resolved_packages, r2.resolved_packages)

    def test_suite(self):
        """Test creation of suite."""
        r = ResolvedContext(["hello_world"])
        suite_dir = os.path.join(self.root, "mysuite")
        r.add_to_suite(suite_dir, "hello1")
        r.add_to_suite(suite_dir, "hello2", prefix="whoah_")
        r.add_to_suite(suite_dir, suffix="_dude")

        for cmd in ("hello_world", "whoah_hello_world", "hello_world_dude"):
            exe = os.path.join(suite_dir, "bin", cmd)
            self.assertTrue(os.path.exists(exe), "should exist: %s" % exe)
            p = subprocess.Popen([exe])
            p.wait()
            self.assertEqual(p.returncode, 0)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestContext("test_create_context"))
    suite.addTest(TestContext("test_execute_command"))
    suite.addTest(TestContext("test_serialize"))
    suite.addTest(TestContext("test_suite"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
