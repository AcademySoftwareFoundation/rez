import inspect
import os.path
import sys
import shutil
import yaml
import unittest

_test_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))

def get_test_dir():
    return _test_dir

def setup_pythonpath():
    sys.path.insert(0, os.path.join(_test_dir, '..', 'python'))

class BaseTest(object):
    """
    Sandbox a set of packages for testing.

    Not a unittest.TestCase: only for use with nose.
    """
    def setUp(self):
        self.packages_dir = os.path.join(_test_dir, 'packages')
        self.packages_dir = os.path.abspath(self.packages_dir)
        self.release_path = os.path.join(self.packages_dir, 'release')
        self.local_path = os.path.join(self.packages_dir, 'local')

        from rez.settings import settings
        settings.set("local_packages_path", self.local_path)
        settings.set("release_packages_path", self.release_path)
        settings.set("packages_path", [self.release_path, self.local_path])

    def cleanup(self):
        """
        delete any pre-existing packages in the sandbox for this test
        """
        if os.path.exists(self.packages_dir):
            shutil.rmtree(self.packages_dir)


class BaseUnitTest(BaseTest, unittest.TestCase):
    pass

#---------------------------------------
# Package Generation
#---------------------------------------


# This code can be used to regenerate the test packages.  Originally,
# each package was intended to dynamically generate its own sandboxed test
# packages, but it is becoming clear that a single curated set will be easier to
# maintain.

def create_packages(local_path, release_path):
    from rez.package_maker import make_yaml_package

    # real world examples are so much easier to follow
    with make_yaml_package('python-2.7.4', local_path) as pkg:
        pkg['variants'] = [['platform-linux'],
                           ['platform-darwin']]

    with make_yaml_package('python-2.6.4', release_path) as pkg:
        pkg['variants'] = [['platform-linux'],
                           ['platform-darwin']]

    with make_yaml_package('python-2.6.1', release_path) as pkg:
        pkg['variants'] = [['platform-linux'],
                           ['platform-darwin']]

    with make_yaml_package('mercurial-3.0', release_path) as pkg:
        pkg['variants'] = [['platform-linux', 'python-2.7'],
                           ['platform-linux', 'python-2.6'],
                           ['platform-darwin', 'python-2.7']]

    with make_yaml_package('maya-2012', release_path) as pkg:
        pkg['requires'] = ['python-2.6']
        pkg['variants'] = [['platform-linux'],
                           ['platform-darwin']]

    with make_yaml_package('maya-2013', release_path) as pkg:
        pkg['requires'] = ['python-2.6']
        pkg['variants'] = [['platform-linux'],
                           ['platform-darwin']]
        pkg['tools'] = ['maya', 'mayapy']

    with make_yaml_package('maya-2014', release_path) as pkg:
        pkg['requires'] = ['python-2.7']
        pkg['variants'] = [['platform-linux'],
                           ['platform-darwin']]
        pkg['tools'] = ['maya', 'mayapy']

    with make_yaml_package('nuke-7.1.2', release_path) as pkg:
        pkg['requires'] = ['python-2.6']
        pkg['tools'] = ['Nuke']

    with make_yaml_package('arnold-4.0.16.0', release_path) as pkg:
        pkg['requires'] = ['python']
        pkg['variants'] = [['platform-linux'],
                           ['platform-darwin']]
        pkg['tools'] = ['kick']

    with make_yaml_package('mtoa-0.25.0', release_path) as pkg:
        #pkg['requires'] = ['arnold-4.0.16']
        pkg['variants'] = [['platform-linux', 'maya-2014', 'arnold-4.0.15+'],
                           ['platform-linux', 'maya-2013', 'arnold-4.0.15+'],
                           ['platform-darwin', 'maya-2014', 'arnold-4.0.15+'],
                           ['platform-darwin', 'maya-2013', 'arnold-4.0.15+']]

    with make_yaml_package('mtoa-0.25.0', release_path) as pkg:
        #pkg['requires'] = ['arnold-4.0.16']
        pkg['variants'] = [['platform-linux', 'maya-2014', 'arnold-4.0.15+'],
                           ['platform-linux', 'maya-2013', 'arnold-4.0.15+'],
                           ['platform-darwin', 'maya-2014', 'arnold-4.0.15+'],
                           ['platform-darwin', 'maya-2013', 'arnold-4.0.15+']]

    with make_yaml_package('platform-linux', release_path):
        pass
    with make_yaml_package('platform-darwin', release_path):
        pass

    with make_yaml_package('arch-x86_64', release_path):
        pass
    with make_yaml_package('arch-i386', release_path):
        pass

    # versionless
    with make_yaml_package('site', release_path) as pkg:
        pkg['requires'] = ['maya', 'nuke-7']
