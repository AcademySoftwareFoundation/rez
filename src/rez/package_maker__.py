from rez.utils.schema import Required, schema_keys
from rez.utils.formatting import PackageRequest
from rez.utils.data_utils import SourceCode, AttrDictWrapper
from rez.serialise import FileFormat
from rez.package_resources_ import help_schema, _commands_schema
from rez.package_serialise import dump_package_data
from rez.package_repository import create_memory_package_repository
from rez.packages_ import Package
from rez.vendor.schema.schema import Schema, Optional, Or, Use, And
from rez.vendor.version.version import Version
from contextlib import contextmanager
import os.path
import os


package_request_schema = Or(basestring,
                            And(PackageRequest, Use(str)))


package_schema = Schema({
    Required("name"):                   basestring,
    Optional("base"):                   basestring,
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

    Optional('pre_commands'):           _commands_schema,
    Optional('commands'):               _commands_schema,
    Optional('post_commands'):          _commands_schema,

    Optional('custom'):                 dict,

    Optional(basestring):               object  # allows deprecated fields
})


package_schema_keys = schema_keys(package_schema)


class PackageMaker(AttrDictWrapper):
    """Utility class for creating packages."""
    def __init__(self, name, data=None):
        """Create a package maker.

        Args:
            name (str): Package name.
        """
        super(PackageMaker, self).__init__(data)
        self.name = name

    def get_package(self):
        """Create the analogous package.

        Returns:
            `Package` object.
        """
        # get and validate package data
        package_data = self._get_data()
        package_data = package_schema.validate(package_data)

        # create a 'memory' package repository containing just this package
        version_str = package_data.get("version") or "_NO_VERSION"
        repo_data = {self.name: {version_str: package_data}}
        repo = create_memory_package_repository(repo_data)

        # retrieve the package from the new repository
        family_resource = repo.get_package_family(self.name)
        it = repo.iter_packages(family_resource)
        package_resource = it.next()
        package = Package(package_resource)

        # revalidate the package for extra measure
        package.validate_data()
        return package

    def _get_data(self):
        data = self._data.copy()
        data = dict((k, v) for k, v in data.iteritems() if v is not None)
        return data


@contextmanager
def make_package(name, path, make_base=None, make_root=None):
    """Make and install a package.

    Example:

        >>> def make_root(variant, path):
        >>>     os.symlink("/foo_payload/misc/python27", "ext")
        >>>
        >>> with make_package('foo', '/packages', make_root=make_root) as pkg:
        >>>     pkg.version = '1.0.0'
        >>>     pkg.description = 'does foo things'
        >>>     pkg.requires = ['python-2.7']

    Args:
        name (str): Package name.
        path (str): Package repository path to install package into.
        make_base (callable): Function that is used to create the package
            payload, if applicable.
        make_root (callable): Function that is used to create the package
            variant payloads, if applicable.

    Note:
        Both `make_base` and `make_root` are called once per variant install,
        and have the signature (variant, path).
    """
    maker = PackageMaker(name)
    yield maker

    # post-with-block:
    package = maker.get_package()
    cwd = os.getcwd()
    for variant in package.iter_variants():
        variant_ = variant.install(path)

        base = variant_.base
        if make_base and base:
            if not os.path.exists(base):
                os.makedirs(base)
            os.chdir(base)
            make_base(variant_, base)

        root = variant_.root
        if make_root and root:
            if not os.path.exists(root):
                os.makedirs(root)
            os.chdir(root)
            make_root(variant_, root)
    os.chdir(cwd)