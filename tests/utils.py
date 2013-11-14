import inspect
import os.path
import sys
import shutil
import yaml

_test_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))

def get_test_dir():
    return _test_dir

sys.path.insert(0, os.path.join(_test_dir, '..', 'python'))

def make_version(path, name, version=None, requires=None, variants=None):
    data = {}
    data['name'] = name
    data['config_version'] = 0
    if version:
        data['version'] = version
        basedir = os.path.join(path, name, version)
    else:
        basedir = os.path.join(path, name)
    if requires:
        data['requires'] = requires

    os.makedirs(basedir)

    if variants:
        data['variants'] = variants
        for variant in variants:
            os.makedirs(os.path.join(basedir, *variant))
    metafile = os.path.join(basedir, 'package.yaml')
    

    with open(metafile, 'w') as f:
        yaml.dump(data, f)

class RezTest(object):
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

        import rez.rez_filesys as fs
        fs._g_local_pkgs_path = self.local_path
        fs._g_syspaths = [self.release_path, self.local_path]
        fs._g_syspaths_nolocal = [self.release_path]

    def make_local_package(self, name, version=None, requires=None, variants=None):
        make_version(self.local_path, name, version, requires, variants)

    def make_release_package(self, name, version=None, requires=None, variants=None):
        make_version(self.release_path, name, version, requires, variants)

    def cleanup(self):
        if os.path.exists(self.packages_dir):
            shutil.rmtree(self.packages_dir)
