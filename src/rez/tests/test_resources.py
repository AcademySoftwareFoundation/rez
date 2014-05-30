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
    return set(_abspath(path) for path in it)

def _abstuple(r):
    return (r[0], r[1], _abspath(r[2]))

def _abstuples(it):
    return set(_abstuple(r) for r in it)

def _to_paths(it):
    return _abspaths(r.path for r in it)

def _to_tuples(it):
    entries = set()
    for r in it:
        e = [r.__class__.__name__, str(r.get("version", "-")),
             _abspath(r.path)]
        entries.add(tuple(e))
    return entries

ALL_PACKAGES = _abspaths([
    'packages/bad/1/package.yaml',
    'packages/whack/2.0.0/package.yaml',

    'packages/unversioned/package.yaml',
    'packages/versioned/1.0/package.yaml',
    'packages/versioned/2.0/package.yaml',
    'packages/single_unversioned.yaml',
    'packages/single_versioned.yaml',
    'packages/multi.yaml',

    'pypackages/unversioned/package.py',
    'pypackages/versioned/1.0/package.py',
    'pypackages/versioned/2.0/package.py',
    'pypackages/single_unversioned.py',
    'pypackages/single_versioned.py',
    'pypackages/multi.py'])

ALL_FOLDERS = _abspaths([
    'packages/unversioned',
    'packages/bad',
    'packages/bad/1',
    'packages/whack',
    'packages/whack/2.0.0',

    'packages/versioned',
    'packages/versioned/1.0',
    'packages/versioned/2.0',

    'pypackages/unversioned',
    'pypackages/versioned',
    'pypackages/versioned/1.0',
    'pypackages/versioned/2.0'])


ALL_RESOURCES = _abstuples([
    ('NameFolder', '-', 'pypackages/unversioned'),
    ('NameFolder', '-', 'pypackages/versioned'),
    ('NameFolder', '-', 'packages/versioned'),
    ('NameFolder', '-', 'packages/unversioned'),
    ('NameFolder', '-', 'packages/bad'),
    ('NameFolder', '-', 'packages/whack'),

    ('VersionFolder', '1.0', 'pypackages/versioned/1.0'),
    ('VersionFolder', '2.0', 'pypackages/versioned/2.0'),
    ('VersionFolder', '1.0', 'packages/versioned/1.0'),
    ('VersionFolder', '2.0', 'packages/versioned/2.0'),
    ('VersionFolder', '1', 'packages/bad/1'),
    ('VersionFolder', '2.0.0', 'packages/whack/2.0.0'),

    ('VersionlessPackageResource', '-', 'pypackages/unversioned/package.py'),
    ('VersionlessPackageResource', '-', 'packages/unversioned/package.yaml'),

    ('VersionedPackageResource', '1.0', 'pypackages/versioned/1.0/package.py'),
    ('VersionedPackageResource', '2.0', 'pypackages/versioned/2.0/package.py'),
    ('VersionedPackageResource', '1.0', 'packages/versioned/1.0/package.yaml'),
    ('VersionedPackageResource', '2.0', 'packages/versioned/2.0/package.yaml'),
    ('VersionedPackageResource', '1', 'packages/bad/1/package.yaml'),
    ('VersionedPackageResource', '2.0.0', 'packages/whack/2.0.0/package.yaml'),

    ('CombinedPackageFamilyResource', '-', 'packages/single_unversioned.yaml'),
    ('CombinedPackageFamilyResource', '-', 'pypackages/single_unversioned.py'),
    ('CombinedPackageFamilyResource', '-', 'packages/single_versioned.yaml'),
    ('CombinedPackageFamilyResource', '-', 'pypackages/single_versioned.py'),
    ('CombinedPackageFamilyResource', '-', 'packages/multi.yaml'),
    ('CombinedPackageFamilyResource', '-', 'pypackages/multi.py'),

    ('CombinedPackageResource', '', 'packages/single_unversioned.yaml'),
    ('CombinedPackageResource', '', 'pypackages/single_unversioned.py'),
    ('CombinedPackageResource', '3.5', 'packages/single_versioned.yaml'),
    ('CombinedPackageResource', '3.5', 'pypackages/single_versioned.py'),
    ('CombinedPackageResource', '1.0', 'packages/multi.yaml'),
    ('CombinedPackageResource', '1.1', 'packages/multi.yaml'),
    ('CombinedPackageResource', '1.2', 'packages/multi.yaml'),
    ('CombinedPackageResource', '1.0', 'pypackages/multi.py'),
    ('CombinedPackageResource', '1.1', 'pypackages/multi.py'),
    ('CombinedPackageResource', '1.2', 'pypackages/multi.py')])


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

        self.assertEqual(resources.CombinedPackageResource.parents(),
                         (resources.PackagesRoot,
                          resources.CombinedPackageFamilyResource))

        # order is determined by the order in which resources were registered
        # which ultimately does not matter. hence, we test with sets.
        self.assertEqual(set(resources.NameFolder.children()),
                         set((resources.VersionFolder,
                              resources.VersionlessPackageResource)))

    def test_2(self):
        """basic iteration"""

        # iterate over explicit resource type
        result = list(iter_resources(0, resource_keys=['package.versionless']))
        self.assertEqual(_to_paths(result),
                         _abspaths(['packages/unversioned/package.yaml',
                                    'pypackages/unversioned/package.py']))

        # iterate over explicit resource type, specifying 'name' variable. Also
        # check that expanded variables in the result are correct.
        result = list(iter_resources(0, resource_keys=['package.versioned'],
                                     variables=dict(name='versioned')))
        self.assertEqual(_to_paths(result),
                         _abspaths(['packages/versioned/1.0/package.yaml',
                                    'packages/versioned/2.0/package.yaml',
                                    'pypackages/versioned/1.0/package.py',
                                    'pypackages/versioned/2.0/package.py']))

        path = _abspath('packages/versioned/1.0/package.yaml')
        resource = [r for r in result if r.path == path][0]
        self.assertEqual(resource.variables,
                         {'name': 'versioned',
                          'version': '1.0',
                          'ext': 'yaml',
                          'search_path': self.packages_path})

        # iterate over several explicit resource types
        result = list(iter_resources(0, resource_keys=['package.versionless',
                                                       'package.versioned']))
        self.assertEqual(_to_paths(result),
                         _abspaths(['packages/unversioned/package.yaml',
                                    'pypackages/unversioned/package.py',
                                    'packages/versioned/1.0/package.yaml',
                                    'packages/versioned/2.0/package.yaml',
                                    'pypackages/versioned/1.0/package.py',
                                    'pypackages/versioned/2.0/package.py',
                                    # error in metadata only, so iteration ok
                                    'packages/bad/1/package.yaml',
                                    'packages/whack/2.0.0/package.yaml']))

        # iterate over glob pattern of resource types
        result = list(iter_resources(0, resource_keys=['package.*']))
        self.assertEqual(_to_paths(result), ALL_PACKAGES)

        result = list(iter_resources(0, resource_keys=['folder.*']))
        self.assertEqual(_to_paths(result), ALL_FOLDERS)

        # iterate over all resources
        result = list(iter_resources(0))
        self.assertEqual(_to_tuples(result), ALL_RESOURCES)

    def test_3(self):
        """resource loading"""

        # find a resource given a set of variables, check data is as expected
        resource = get_resource(0, resource_keys=['package.*'],
                                variables=dict(name='versioned',
                                               version='1.0',
                                               ext='py'))

        expected_variables = {'name': 'versioned',
                              'version': '1.0',
                              'ext': 'py',
                              'search_path': self.pypackages_path}

        expected_data = {'config_version': 0,
                         'description': 'this description spans multiple lines.',
                         'name': 'versioned',
                         'requires': ['amaze', 'wow'],
                         'timestamp': 0,
                         'tools': ['amazeballs'],
                         'version': Version('1.0')}

        path = _abspath('pypackages/versioned/1.0/package.py')
        self.assertEqual(resource.path, path)
        self.assertEqual(resource.variables, expected_variables)
        self.assertEqual(resource.load(), expected_data)

        # load the same resource given a filepath rather than variables
        resource = get_resource(0, filepath=path)
        self.assertEqual(resource.path, path)
        self.assertEqual(resource.variables, expected_variables)
        self.assertEqual(resource.load(), expected_data)

        # find the same resource but from different resource types (py, yaml)
        # and verify that they are the same
        for resource in iter_resources(0, resource_keys=['package.*'],
                                       variables=dict(name='versioned',
                                                      version='1.0')):
            self.assertEqual(resource.load(), expected_data)

        # iterate over packages in a combined family package, test that the
        # version override feature is working
        def _expected_data(version):
            tool = "twerk" if version >= Version("1.1") else "tweak"
            return {'config_version': 0,
                    'name': 'multi',
                    'version': version,
                    'tools': [tool]}

        resources = list(iter_resources(0, resource_keys=['package.combined'],
                                        variables=dict(name='multi')))
        for resource in resources:
            expected_data = _expected_data(Version(resource.get("version")))
            self.assertEqual(resource.load(), expected_data)

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
                                         version='1'))

        with self.assertRaises(PackageMetadataError):
            # the resource version key does not match the versioned folder
            load_resource(0, resource_keys=['package.*'],
                          variables=dict(name='whack',
                                         version='2.0.0'))

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
