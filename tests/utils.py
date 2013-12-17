import inspect
import os.path
import sys
import shutil
import yaml

_test_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))

def get_test_dir():
    return _test_dir

def setup_pythonpath():
    sys.path.insert(0, os.path.join(_test_dir, '..', 'python'))

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

class PackageMaker(object):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass
    
    def _make(self, path):
        metadata = self.__dict__.copy()
        for key in metadata.keys():
            if key.startswith('_'):
                metadata.pop(key)
        make_version(path, metadata)

class BaseTest(object):
    """
    Sandbox a set of packages for testing
    """
    def __init__(self):
        self.packages_dir = os.path.join(_test_dir,
                                         self.__class__.__name__,
                                         'packages')
        self.packages_dir = os.path.abspath(self.packages_dir)
        self.release_path = os.path.join(self.packages_dir, 'release')
        self.local_path = os.path.join(self.packages_dir, 'local')
        self.local_packages = {}
        self.release_packages = {}

        import rez.filesys as fs
        fs._g_local_pkgs_path = self.local_path
        fs._g_syspaths = [self.release_path, self.local_path]
        fs._g_syspaths_nolocal = [self.release_path]

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
            pkg._make(self.local_path)
        for pkg in self.release_packages.values():
            pkg._make(self.release_path)

    def cleanup(self):
        """
        delete any pre-existing packages in the sandbox for this test
        """
        if os.path.exists(self.packages_dir):
            shutil.rmtree(self.packages_dir)
