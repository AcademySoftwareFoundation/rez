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

class PackageMaker(object):
    """
    Context manager that holds metadata for creating the package file
    """
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

class PackagesMaker(object):
    def __init__(self, local_path, release_path):
        self.local_packages = {}
        self.release_packages = {}
        self.release_path = release_path
        self.local_path = local_path

    def make(self, pkg_maker, path):
        metadata = pkg_maker.__dict__.copy()
        for key in metadata.keys():
            if key.startswith('_'):
                metadata.pop(key)
        self.make_version(path, metadata)

    @staticmethod
    def make_version(path, metadata):
        name = metadata['name']
        metadata.setdefault('config_version', 0)
        if 'version' in metadata:
            basedir = os.path.join(path, name, metadata['version'])
        else:
            basedir = os.path.join(path, name)

        os.makedirs(basedir)

        if 'variants' in metadata:
            for variant in metadata['variants']:
                os.makedirs(os.path.join(basedir, *variant))
        metafile = os.path.join(basedir, 'package.yaml')

        with open(metafile, 'w') as f:
            yaml.dump(metadata, f)

    def add_package(self, name, local=False):
        """
        Add a package to make on disk for the test.

        After all individual packages have been added using add_package(),
        call make_packages to create them on disk. The actions are separated
        so that subclasses can override certain packages with their own variations
        before they are created.
        """
        pkg = PackageMaker()
        parts = name.split('-')
        if len(parts) == 1:
            pkg.name = parts[0]
        else:
            pkg.name, pkg.version = parts

        if local:
            self.local_packages[name] = pkg
        else:
            self.release_packages[name] = pkg
        return pkg

    def make_packages(self):
        """
        make on disk all of the added packages via add_package().
        """
        for pkg in self.local_packages.values():
            self.make(pkg, self.local_path)
        for pkg in self.release_packages.values():
            self.make(pkg, self.release_path)

def create_packages(local_path, release_path):
    pkgs = PackagesMaker(local_path, release_path)
    # real world examples are so much easier to follow
    with pkgs.add_package('python-2.7.4', local=True) as pkg:
        pkg.variants = [['platform-linux'],
                        ['platform-darwin']]

    with pkgs.add_package('python-2.6.4') as pkg:
        pkg.variants = [['platform-linux'],
                        ['platform-darwin']]

    with pkgs.add_package('python-2.6.1') as pkg:
        pkg.variants = [['platform-linux'],
                        ['platform-darwin']]

    with pkgs.add_package('mercurial-3.0') as pkg:
        pkg.variants = [['platform-linux', 'python-2.7'],
                        ['platform-linux', 'python-2.6'],
                        ['platform-darwin', 'python-2.7']]

    with pkgs.add_package('maya-2012') as pkg:
        pkg.requires = ['python-2.6']
        pkg.variants = [['platform-linux'],
                        ['platform-darwin']]

    with pkgs.add_package('maya-2013') as pkg:
        pkg.requires = ['python-2.6']
        pkg.variants = [['platform-linux'],
                        ['platform-darwin']]
        pkg.tools = ['maya', 'mayapy']

    with pkgs.add_package('maya-2014') as pkg:
        pkg.requires = ['python-2.7']
        pkg.variants = [['platform-linux'],
                        ['platform-darwin']]
        pkg.tools = ['maya', 'mayapy']

    with pkgs.add_package('nuke-7.1.2') as pkg:
        pkg.requires = ['python-2.6']
        pkg.tools = ['Nuke']

    with pkgs.add_package('arnold-4.0.16.0') as pkg:
        pkg.requires = ['python']
        pkg.variants = [['platform-linux'],
                        ['platform-darwin']]
        pkg.tools = ['kick']

    with pkgs.add_package('mtoa-0.25.0') as pkg:
        #pkg.requires = ['arnold-4.0.16']
        pkg.variants = [['platform-linux', 'maya-2014', 'arnold-4.0.15+'],
                        ['platform-linux', 'maya-2013', 'arnold-4.0.15+'],
                        ['platform-darwin', 'maya-2014', 'arnold-4.0.15+'],
                        ['platform-darwin', 'maya-2013', 'arnold-4.0.15+']]

    pkgs.add_package('platform-linux')
    pkgs.add_package('platform-darwin')

    pkgs.add_package('arch-x86_64')
    pkgs.add_package('arch-i386')

    # versionless
    with pkgs.add_package('site') as pkg:
        pkg.requires = ['maya', 'nuke-7']

    pkgs.make_packages()
