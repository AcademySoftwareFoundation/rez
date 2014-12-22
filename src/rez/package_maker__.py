from rez.utils.schema import Required, schema_keys
from rez.utils.formatting import PackageRequest
from rez.utils.data_utils import SourceCode
from rez.serialise import FileFormat
from rez.package_resources_ import help_schema
from rez.package_serialise import dump_package_data
from rez.package_repository import create_memory_package_repository
from rez.packages_ import Package
from rez.vendor.schema.schema import Schema, Optional, Or, Use, And
from rez.vendor.version.version import Version
from inspect import isfunction, ismethod
from tempfile import mkdtemp


package_request_schema = Or(basestring,
                            And(PackageRequest, Use(str)))


package_schema = Schema({
    Required("name"):                   basestring,
    Optional("version"):                Or(basestring,
                                           And(Version, Use(str))),
    Optional('description'):            basestring,
    Optional('authors'):                [basestring],

    Optional('requires'):               [package_request_schema],
    Optional('build_requires'):         [package_request_schema],
    Optional('private_build_requires'): [package_request_schema],
    Optional('variants'):               [[package_request_schema]],

    Optional('uuid'):                   basestring,
    Optional('config'):                 dict,
    Optional('tools'):                  [basestring],
    Optional('help'):                   help_schema,

    Optional('pre_commands'):           callable,
    Optional('commands'):               callable,
    Optional('post_commands'):          callable,

    Optional('custom'):                 dict
})


package_schema_keys = schema_keys(package_schema)


class PackageMaker(object):
    """Utility class for creating packages.

    You can either create an instance of `PackageMaker` directly, passing all
    relevant package attributes in the constructor; or, you can subclass it, and
    any package attributes you define on the subclass are used as well (and are
    used in preference to `self.data`).

    Example:

        class FooPackageMaker(PackageMaker):
            description = "Does foo-like things."

            def __init__(self, data):
                super(FooPackageMaker, self).__init__("foo", data)

            def commands(self):
                # this code must be self-contained!
                env.PATH.append("{root}/bin")
    """
    def __init__(self, name, data):
        """Create a package maker.

        Args:
            name (str): Package name.
            data (dict): Package data. Must conform to `package_schema`.
        """
        self.name = name
        self._data = data

    def get_package(self):
        """Create the analogous package.

        Returns:
            `Package` object.
        """
        # get and validate package data
        package_data = self._get_data()
        package_data = package_schema.validate(package_data)
        package_data = self._post_transform_data(package_data)

        # create a 'memory' package repository containing just this package. We
        # don't do this via `package_repository_manager` because we don't want
        # the associated resources to be cached.
        version_str = package_data.get("version") or "_NO_VERSION"
        repo_data = {self.name: {version_str: package_data}}
        repo = create_memory_package_repository(repo_data)

        # retrieve the package from the new repository
        family_resource = repo.get_package_family(self.name)
        it = repo.iter_packages(family_resource)
        package_resource = it.next()
        package = Package(package_resource)
        return package

        """
        # turn into a developer package in a tmpdir
        path = mkdtemp(prefix="rez_package_maker_")
        filepath = os.path.join(path, "package.py")
        with open(filepath, 'w') as f:
            dump_package_data(package_data, f, FileFormat.py)

        package = get_developer_package(path)
        return package
        """

    def _get_data(self):
        data = self._data.copy()

        for key in package_schema_keys:
            value = getattr(self, key, None)
            if value is not None:
                data[key] = value

    # schema expected by the 'memory' package repository is a little different
    # to the schema we expect in the package maker.
    def _post_transform_data(self, data):
        data_ = {}
        for key, value in data.iteritems():
            if isfunction(value) or ismethod(value):
                value = SourceCode.from_function(value)

            data_[key] = value
        return data_
