"""
Pre-release hook checking if the package contains test that need to be run successfully before unleashing the package
"""
import subprocess
import os

from rez.release_hook import ReleaseHook
from rez.exceptions import ReleaseHookCancellingError

from rez.utils.logging_ import print_debug


class RezTestReleaseHook(ReleaseHook):

    @classmethod
    def name(cls):
        return "rez_test"

    def __init__(self, source_path):
        super(RezTestReleaseHook, self).__init__(source_path)

    def post_release(self, install_path='', **kwargs):

        tests = self.package.tests
        testPath = list(self.package.config.nonlocal_packages_path)
        testPath.insert(0, install_path)

        if tests:
            for testName, testDetails in tests.iteritems():

                args = ['rez', 'test', "%s==%s"%(self.package.name, self.package.version), testName]

                retcode = self._run_command(args, testPath)

                if retcode:
                    raise ReleaseHookCancellingError(
                        "Running %s test (command: %s) returned code %s\n" % (testName, testDetails['command'], retcode))
        else:
            print_debug("Package does not have rez test. Continuing with release ...", module="hooks")

    def _run_command(self, args, packages_path):
        cmd_str = ' '.join(args)
        packages_path_str = os.path.pathsep.join(packages_path)

        test_env = os.environ.copy()
        test_env['REZ_PACKAGES_PATH'] = packages_path_str

        print_debug("Running: REZ_PACKAGES_PATH=%s %s" % (packages_path_str, cmd_str), module="hooks")

        p = subprocess.Popen(args, env=test_env)
        p.wait()
        return p.returncode


def register_plugin():
    return RezTestReleaseHook
