from rez.utils._version import _rez_Version
from rez.utils.schema import Required, schema_keys
from rez.utils.filesystem import retain_cwd
from rez.utils.formatting import PackageRequest
from rez.utils.data_utils import AttrDictWrapper
from rez.utils.logging_ import print_warning
from rez.exceptions import PackageMetadataError
from rez.package_resources_ import help_schema, _commands_schema, \
    _function_schema, late_bound
from rez.package_repository import create_memory_package_repository
from rez.packages_ import Package
from rez.package_py_utils import expand_requirement
from rez.vendor.schema.schema import Schema, Optional, Or, Use, And
from rez.vendor.version.version import Version
from rez.vendor.six import six
from contextlib import contextmanager
import os

# Backwards compatibility with Python 2
basestring = six.string_types[0]

# this schema will automatically harden request strings like 'python-*'; see
# the 'expand_requires' function for more info.
#
package_request_schema = Or(And(basestring, Use(expand_requirement)),
                            And(PackageRequest, Use(str)))

tests_schema = Schema({
    Optional(basestring): Or(
        Or(basestring, [basestring]),
        {
            "command": Or(basestring, [basestring]),
            Optional("requires"): [package_request_schema]
        }
    )
})


package_schema = Schema({
    Optional("requires_rez_version"):   And(basestring, Use(Version)),

    Required("name"):                   basestring,
    Optional("base"):                   basestring,
    Optional("version"):                Or(basestring,
                                           And(Version, Use(str))),
    Optional('description'):            basestring,
    Optional('authors'):                [basestring],

    Optional('requires'):               late_bound([package_request_schema]),
    Optional('build_requires'):         late_bound([package_request_schema]),
    Optional('private_build_requires'): late_bound([package_request_schema]),

    # deliberately not possible to late bind
    Optional('variants'):               [[package_request_schema]],

    Optional('relocatable'):            late_bound(Or(None, bool)),
    Optional('hashed_variants'):        bool,

    Optional('uuid'):                   basestring,
    Optional('config'):                 dict,
    Optional('tools'):                  late_bound([basestring]),
    Optional('help'):                   late_bound(help_schema),

    Optional('tests'):                  late_bound(tests_schema),

    Optional('pre_commands'):           _commands_schema,
    Optional('commands'):               _commands_schema,
    Optional('post_commands'):          _commands_schema,

    # attributes specific to pre-built packages
    Optional("build_system"):           basestring,
    Optional("build_command"):          Or([basestring], basestring, False),
    Optional("preprocess"):             _function_schema,

    # arbitrary fields
    Optional(basestring):               object
})


class PackageMaker(AttrDictWrapper):
    """Utility class for creating packages."""
    def __init__(self, name, data=None, package_cls=None):
        """Create a package maker.

        Args:
            name (str): Package name.
        """
        super(PackageMaker, self).__init__(data)
        self.name = name
        self.package_cls = package_cls or Package

        # set by `make_package`
        self.installed_variants = []
        self.skipped_variants = []

    def get_package(self):
        """Create the analogous package.

        Returns:
            `Package` object.
        """
        # get and validate package data
        package_data = self._get_data()
        package_data = package_schema.validate(package_data)

        # check compatibility with rez version
        if "requires_rez_version" in package_data:
            ver = package_data.pop("requires_rez_version")

            if _rez_Version < ver:
                raise PackageMetadataError(
                    "Failed reading package definition file: rez version >= %s "
                    "needed (current version is %s)" % (ver, _rez_Version))

        # create a 'memory' package repository containing just this package
        version_str = package_data.get("version") or "_NO_VERSION"
        repo_data = {self.name: {version_str: package_data}}
        repo = create_memory_package_repository(repo_data)

        # retrieve the package from the new repository
        family_resource = repo.get_package_family(self.name)
        it = repo.iter_packages(family_resource)
        package_resource = next(it)

        package = self.package_cls(package_resource)

        # revalidate the package for extra measure
        package.validate_data()
        return package

    def _get_data(self):
        data = self._data.copy()

        data.pop("installed_variants", None)
        data.pop("skipped_variants", None)
        data.pop("package_cls", None)

        data = dict((k, v) for k, v in data.items() if v is not None)
        return data


@contextmanager
def make_package(name, path, make_base=None, make_root=None, skip_existing=True,
                 warn_on_skip=True):
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
        skip_existing (bool): If True, detect if a variant already exists, and
            skip with a warning message if so.
        warn_on_skip (bool): If True, print warning when a variant is skipped.

    Yields:
        `PackageMaker` object.

    Note:
        Both `make_base` and `make_root` are called once per variant install,
        and have the signature (variant, path).

    Note:
        The 'installed_variants' attribute on the `PackageMaker` instance will
        be appended with variant(s) created by this function, if any.
    """
    maker = PackageMaker(name)
    yield maker

    # post-with-block:
    #

    package = maker.get_package()
    cwd = os.getcwd()
    src_variants = []

    # skip those variants that already exist
    if skip_existing:
        for variant in package.iter_variants():
            variant_ = variant.install(path, dry_run=True)
            if variant_ is None:
                src_variants.append(variant)
            else:
                maker.skipped_variants.append(variant_)
                if warn_on_skip:
                    print_warning("Skipping installation: Package variant already "
                                  "exists: %s" % variant_.uri)
    else:
        src_variants = package.iter_variants()

    with retain_cwd():
        # install the package variant(s) into the filesystem package repo at `path`
        for variant in src_variants:
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

            maker.installed_variants.append(variant_)


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
