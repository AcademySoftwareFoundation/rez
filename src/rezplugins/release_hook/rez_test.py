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

                args = ['rez', 'test', self.package.name, testName]

                stdout, stderr, retcode = self._run_command(args, testPath)

                if retcode:
                    raise ReleaseHookCancellingError(
                        "Running %s test (command: %s) returned code %s\n" % (testName, testDetails['command'], retcode))
                else:
                    print stdout
        else:
            print_debug("Package does not have rez test. Continuing with release ...", module="hooks")

    def _run_command(self, args, packages_path):
        cmd_str = ' '.join(args)
        os.environ['REZ_PACKAGES_PATH'] = os.path.pathsep.join(packages_path)

        print_debug("Running: %s   with packages path %s " % (cmd_str, os.environ['REZ_PACKAGES_PATH']), module="hooks")

        p = subprocess.Popen(args, env=os.environ, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        return stdout, stderr, p.returncode


def register_plugin():
    return RezTestReleaseHook
