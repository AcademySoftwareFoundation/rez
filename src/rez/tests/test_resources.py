import rez.resources as resources
from rez.resources import iter_resources, load_resource, get_resource, \
    ResourceError, PackageMetadataError
from rez.vendor.version.version import Version
from rez.tests.util import TestBase
import os.path
import pprint

ALL_PACKAGES = [
'rez/tests/data/resources/packages/unversioned/package.yaml',
 'rez/tests/data/resources/packages/bad/custom/package.yaml',
 'rez/tests/data/resources/packages/versioned/1.0/package.yaml',
 'rez/tests/data/resources/packages/versioned/2.0/package.yaml',
 'rez/tests/data/resources/packages/multi.yaml',
 'rez/tests/data/resources/pypackages/unversioned/package.py',
 'rez/tests/data/resources/pypackages/versioned/1.0/package.py',
 'rez/tests/data/resources/pypackages/versioned/2.0/package.py',
 'rez/tests/data/resources/pypackages/multi.py']

ALL_FOLDERS = [
 'rez/tests/data/resources/packages/unversioned',
 'rez/tests/data/resources/packages/bad',
 'rez/tests/data/resources/packages/bad/custom',
 'rez/tests/data/resources/packages/versioned',
 'rez/tests/data/resources/packages/versioned/1.0',
 'rez/tests/data/resources/packages/versioned/2.0',
 'rez/tests/data/resources/pypackages/unversioned',
 'rez/tests/data/resources/pypackages/versioned',
 'rez/tests/data/resources/pypackages/versioned/1.0',
 'rez/tests/data/resources/pypackages/versioned/2.0']

def _to_paths(it):
    return [p.path for p in it]

class TestResources(TestBase):
    @classmethod
    def setUpClass(cls):
        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "resources", "packages")
        pypackages_path = os.path.join(path, "data", "resources", "pypackages")

        cls.settings = dict(
            packages_path=[packages_path, pypackages_path])

    def test_1(self):
        "class methods"
        self.assertEqual(resources.VersionlessPackageResource.parents(),
                         (resources.PackagesRoot,
                          resources.NameFolder))

        self.assertEqual(resources.VersionedPackageResource.parents(),
                         (resources.PackagesRoot,
                          resources.NameFolder,
                          resources.VersionFolder))

        # order does not matter
        self.assertEqual(set(resources.NameFolder.children()),
                         set((resources.VersionFolder,
                              resources.VersionlessPackageResource)))

    def test_2(self):
        "basic iteration"
        result = list(iter_resources(0, resource_keys=['package.versionless']))
        self.assertEqual(
            _to_paths(result),
            ['rez/tests/data/resources/packages/unversioned/package.yaml',
             'rez/tests/data/resources/pypackages/unversioned/package.py'])

        result = list(iter_resources(0, resource_keys=['package.versioned'],
                                     name='versioned'))
        self.assertEqual(
            _to_paths(result),
            ['rez/tests/data/resources/packages/versioned/1.0/package.yaml',
             'rez/tests/data/resources/packages/versioned/2.0/package.yaml',
             'rez/tests/data/resources/pypackages/versioned/1.0/package.py',
             'rez/tests/data/resources/pypackages/versioned/2.0/package.py'])
        # check that the expanded variables are correct
        self.assertEqual(result[0].variables,
                         {'name': 'versioned',
                          'version': '1.0',
                          'ext': 'yaml'})

        result = list(iter_resources(0, resource_keys=['package.*']))
        self.assertEqual(_to_paths(result), ALL_PACKAGES)

        result = list(iter_resources(0, resource_keys=['folder.*']))
        self.assertEqual(_to_paths(result), ALL_FOLDERS)

    def test_3(self):
        "resource loading"

        resource = get_resource(0, resource_keys=['package.*'],
                                name='versioned', version='1.0')
        self.assertEquals(
            resource.path,
            'rez/tests/data/resources/packages/versioned/1.0/package.yaml')

        data = resource.load()
        self.assertEqual(
            data,
            {'config_version': 0,
             'description': 'this description spans multiple lines.',
             'name': 'versioned',
             'requires': ['amaze', 'wow'],
             'timestamp': 0,
             'tools': ['amazeballs'],
             'version': Version('1.0')}
        )

        resource = get_resource(0, resource_keys=['package.*'],
                                name='versioned', version='1.0', ext='py')
        self.assertEqual(data, resource.load())

        with self.assertRaises(PackageMetadataError):
            # the resource has a mismatch between the folder version and the
            # version in the file
            load_resource(0, resource_keys=['package.*'],
                          name='versioned', version='2.0', ext='yaml')

        with self.assertRaises(PackageMetadataError):
            # the resource has a custom key at the root
            load_resource(0, resource_keys=['package.*'],
                          name='bad', version='custom')

        fullpath = 'rez/tests/data/resources/packages/versioned/2.0/package.yaml'
        # fullpath = os.path.abspath(fullpath)
        resource = get_resource(0, filepath=fullpath)
