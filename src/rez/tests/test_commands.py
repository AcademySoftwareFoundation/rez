from rez.vendor.version.requirement import VersionedObject
from rez.rex import Comment, EnvAction, Shebang, Setenv, Alias, Appendenv
from rez.resolved_context import ResolvedContext
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase
import os


class TestCommands(TestBase):
    # Note some tests use a hardcoded '/' path separator instead of
    # os.path.join.  This is because they are being compared against
    # baked commands in existing package.yaml|py files in the data
    # directory where the separator is static.

    @classmethod
    def get_packages_path(cls):
        path = os.path.realpath(os.path.dirname(__file__))
        return os.path.join(path, "data", "commands", "packages")

    @classmethod
    def setUpClass(cls):
        cls.settings = dict(
            packages_path=[cls.get_packages_path()],
            resolve_caching=False,
            warn_untimestamped=False,
            warn_old_commands=False,
            implicit_packages=[],
            rez_1_environment_variables=False)

    def __init__(self, fn):
        TestBase.__init__(self, fn)
        self.packages_path = self.get_packages_path()

    def _test_package(self, pkg, env, expected_commands):
        orig_environ = os.environ.copy()
        r = ResolvedContext([str(pkg)], caching=False)

        # this environ should not have changed
        self.assertEqual(orig_environ, os.environ)

        commands = r.get_actions(parent_environ=env)
        commands_ = []

        # ignore some commands that don't matter or change depending on system
        ignore_keys = set(["REZ_USED",
                           "REZ_USED_VERSION",
                           "REZ_USED_TIMESTAMP",
                           "REZ_USED_REQUESTED_TIMESTAMP",
                           "REZ_USED_PACKAGES_PATH",
                           "REZ_USED_IMPLICIT_PACKAGES",
                           "PATH"])

        for cmd in commands:
            if isinstance(cmd, (Comment, Shebang)):
                continue
            elif isinstance(cmd, EnvAction) and cmd.key in ignore_keys:
                continue
            else:
                commands_.append(cmd)
        self.assertEqual(commands_, expected_commands)

    def _get_rextest_commands(self, pkg):
        verstr = str(pkg.version)
        base = os.path.join(self.packages_path, "rextest", verstr)
        cmds = [Setenv('REZ_REXTEST_VERSION', verstr),
                Setenv('REZ_REXTEST_BASE', base),
                Setenv('REZ_REXTEST_ROOT', base),
                Setenv('REXTEST_ROOT', base),
                Setenv('REXTEST_VERSION', verstr),
                Setenv('REXTEST_MAJOR_VERSION', str(pkg.version[0])),
                Setenv('REXTEST_DIRS', "/".join([base, "data"])),
                Alias('rextest', 'foobar')]
        return cmds

    def _test_rextest_package(self, version):
        pkg = VersionedObject("rextest-%s" % version)

        cmds = [Setenv('REZ_USED_REQUEST', str(pkg)),
                Setenv('REZ_USED_RESOLVE', str(pkg))]
        cmds += self._get_rextest_commands(pkg)

        self._test_package(pkg, {}, cmds)
        # first prepend should still override
        self._test_package(pkg, {"REXTEST_DIRS": "TEST"}, cmds)

    def test_old_yaml(self):
        """Resolve a yaml-based package with old-style bash commands."""
        self._test_rextest_package("1.1")

    def test_new_yaml(self):
        """Resolve a yaml-based package with new rex commands."""
        self._test_rextest_package("1.2")

    def test_py(self):
        """Resolve a new py-based package with rex commands."""
        self._test_rextest_package("1.3")

    def test_2(self):
        """Resolve a package with a dependency, see that their commands are
        concatenated as expected."""
        pkg = VersionedObject("rextest2-2")
        base = os.path.join(self.packages_path, "rextest", "1.3")
        base2 = os.path.join(self.packages_path, "rextest2", "2")

        cmds = [Setenv('REZ_USED_REQUEST', "rextest2-2"),
                Setenv('REZ_USED_RESOLVE', "rextest-1.3 rextest2-2"),
                # rez's rextest vars
                Setenv('REZ_REXTEST_VERSION', "1.3"),
                Setenv('REZ_REXTEST_BASE', base),
                Setenv('REZ_REXTEST_ROOT', base),
                # rez's rextest2 vars
                Setenv('REZ_REXTEST2_VERSION', '2'),
                Setenv('REZ_REXTEST2_BASE', base2),
                Setenv('REZ_REXTEST2_ROOT', base2),
                # rextest's commands
                Setenv('REXTEST_ROOT', base),
                Setenv('REXTEST_VERSION', "1.3"),
                Setenv('REXTEST_MAJOR_VERSION', "1"),
                Setenv('REXTEST_DIRS', "/".join([base, "data"])),
                Alias('rextest', 'foobar'),
                # rextext2's commands
                Appendenv('REXTEST_DIRS', "/".join([base2, "data2"])),
                Setenv('REXTEST2_REXTEST_VER', '1.3'),
                Setenv('REXTEST2_REXTEST_BASE',
                       os.path.join(self.packages_path, "rextest", "1.3"))]

        self._test_package(pkg, {}, cmds)
        # first prepend should still override
        self._test_package(pkg, {"REXTEST_DIRS": "TEST"}, cmds)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestCommands("test_old_yaml"))
    suite.addTest(TestCommands("test_new_yaml"))
    suite.addTest(TestCommands("test_py"))
    suite.addTest(TestCommands("test_2"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
