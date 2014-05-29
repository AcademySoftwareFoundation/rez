import rez.resources as resources
from rez.resources import iter_resources, load_resource, get_resource, \
    ResourceError, PackageMetadataError
from rez.vendor.version.version import Version
from rez.tests.util import TestBase
import rez.vendor.unittest2 as unittest
import os.path


here = os.path.abspath(os.path.dirname(__file__))
data_root = os.path.join(here, "data", "resources")


def _abspath(path):
    return os.path.join(data_root, path)


def _abspaths(it):
    return set([_abspath(p) for p in it])


def _to_paths(it):
    return _abspaths(p.path for p in it)


ALL_PACKAGES = _abspaths([
    'packages/unversioned/package.yaml',
    'packages/bad/custom/package.yaml',
    'packages/versioned/1.0/package.yaml',
    'packages/versioned/2.0/package.yaml',
    'packages/multi.yaml',
    'pypackages/unversioned/package.py',
    'pypackages/versioned/1.0/package.py',
    'pypackages/versioned/2.0/package.py',
    'pypackages/multi.py'])


ALL_FOLDERS = _abspaths([
    'packages/unversioned',
    'packages/bad',
    'packages/bad/custom',
    'packages/versioned',
    'packages/versioned/1.0',
    'packages/versioned/2.0',
    'pypackages/unversioned',
    'pypackages/versioned',
    'pypackages/versioned/1.0',
    'pypackages/versioned/2.0'])


class TestResources(TestBase):
    @classmethod
    def setUpClass(cls):
        cls.packages_path = os.path.join(data_root, "packages")
        cls.pypackages_path = os.path.join(data_root, "pypackages")

        cls.settings = dict(
            packages_path=[cls.packages_path, cls.pypackages_path],
            warn_untimestamped=False)

    def test_1(self):
        """class methods"""
        self.assertEqual(resources.VersionlessPackageResource.parents(),
                         (resources.PackagesRoot,
                          resources.NameFolder))

        self.assertEqual(resources.VersionedPackageResource.parents(),
                         (resources.PackagesRoot,
                          resources.NameFolder,
                          resources.VersionFolder))

        # todo add combined

        # order is determined by the order in which resources were registered
        # which ultimately does not matter. hence, we test with sets.
        self.assertEqual(set(resources.NameFolder.children()),
                         set((resources.VersionFolder,
                              resources.VersionlessPackageResource)))

    def test_2(self):
        """basic iteration"""
        # TODO add test with missing resource_keys

        result = list(iter_resources(0, resource_keys=['package.versionless']))
        self.assertEqual(
            _to_paths(result),
            _abspaths(['packages/unversioned/package.yaml',
                       'pypackages/unversioned/package.py']))

        result = list(iter_resources(0, resource_keys=['package.versioned'],
                                     variables=dict(name='versioned')))
        self.assertEqual(
            _to_paths(result),
            _abspaths(['packages/versioned/1.0/package.yaml',
                       'packages/versioned/2.0/package.yaml',
                       'pypackages/versioned/1.0/package.py',
                       'pypackages/versioned/2.0/package.py']))

        # check that the expanded variables are correct
        path = _abspath('packages/versioned/1.0/package.yaml')
        resource = [r for r in result if r.path == path][0]

        self.assertEqual(resource.variables,
                         {'name': 'versioned',
                          'version': '1.0',
                          'ext': 'yaml',
                          'search_path': self.packages_path})

        result = list(iter_resources(0, resource_keys=['package.*']))
        self.assertEqual(_to_paths(result), ALL_PACKAGES)

        result = list(iter_resources(0, resource_keys=['folder.*']))
        self.assertEqual(_to_paths(result), ALL_FOLDERS)

    def test_3(self):
        """resource loading"""
        resource = get_resource(0, resource_keys=['package.*'],
                                variables=dict(name='versioned',
                                               version='1.0'))
        self.assertEquals(
            resource.path,
            _abspath('packages/versioned/1.0/package.yaml'))

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
                                variables=dict(name='versioned',
                                               version='1.0',
                                               ext='py'))

        path = _abspath('pypackages/versioned/1.0/package.py')
        self.assertEqual(resource.path, path)
        self.assertEqual(resource.variables,
                         {'name': 'versioned',
                          'version': '1.0',
                          'ext': 'py',
                          'search_path': self.pypackages_path})
        self.assertEqual(data, resource.load())

        # load the same resource starting from file path
        # relative path becomes absolute path
        resource = get_resource(0, filepath=path)
        self.assertEqual(resource.path, path)
        self.assertEqual(resource.variables,
                         {'name': 'versioned',
                          'version': '1.0',
                          'ext': 'py',
                          'search_path': self.pypackages_path})

    def test_4(self):
        """invalid resource loading"""
        with self.assertRaises(PackageMetadataError):
            # the resource has a mismatch between the folder version and the
            # version in the file
            load_resource(0, resource_keys=['package.*'],
                          variables=dict(name='versioned',
                                         version='2.0',
                                         ext='yaml'))

        with self.assertRaises(PackageMetadataError):
            # the resource has a custom key at the root
            load_resource(0, resource_keys=['package.*'],
                          variables=dict(name='bad',
                                         version='custom'))

        with self.assertRaises(ResourceError):
            load_resource(0, resource_keys=['non_existent'])

        with self.assertRaises(ResourceError):
            load_resource(0, filepath='/path/to/nothing')


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestResources("test_1"))
    suite.addTest(TestResources("test_2"))
    suite.addTest(TestResources("test_3"))
    suite.addTest(TestResources("test_4"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
