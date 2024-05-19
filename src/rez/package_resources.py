# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import annotations

from rez.utils.resources import Resource
from rez.utils.schema import Required, schema_keys, extensible_schema_dict
from rez.utils.logging_ import print_warning
from rez.utils.sourcecode import SourceCode
from rez.utils.data_utils import cached_property, AttributeForwardMeta, \
    LazyAttributeMeta
from rez.utils.filesystem import find_matching_symlink
from rez.utils.formatting import PackageRequest
from rez.exceptions import PackageMetadataError, ResourceError
from rez.config import config, Config, create_config
from rez.version import Requirement, Version
from rez.vendor.schema.schema import Schema, SchemaError, Optional, Or, And, Use

from textwrap import dedent
import os.path
from abc import abstractmethod
from hashlib import sha1
from typing import Any, Iterable, Iterator, TYPE_CHECKING
from types import FunctionType, MethodType

if TYPE_CHECKING:
    from rez.packages import Variant


# package attributes created at release time
package_release_keys = (
    "timestamp",
    'revision',
    'changelog',
    'release_message',
    'previous_version',
    'previous_revision',
    'vcs')

# package attributes that we don't install
package_build_only_keys = (
    "requires_rez_version",
    "build_system",
    "build_command",
    "preprocess",
    "pre_build_commands"
)

# package attributes that are rex-based functions
package_rex_keys = (
    "pre_commands",
    "commands",
    "post_commands",
    "pre_build_commands",
    "pre_test_commands",
)


# ------------------------------------------------------------------------------
# utility schemas
# ------------------------------------------------------------------------------

help_schema = Or(str,  # single help entry
                 [[str]])  # multiple help entries

_is_late = And(SourceCode, lambda x: hasattr(x, "_late"))


def late_bound(schema):
    return Or(SourceCode, schema)


# used when 'requires' is late bound
late_requires_schema = Schema([
    Or(PackageRequest, And(str, Use(PackageRequest)))
])


# ------------------------------------------------------------------------------
# schema dicts
# ------------------------------------------------------------------------------

# requirements of all package-related resources
#

base_resource_schema_dict: dict[Schema, Any] = {
    Required("name"): str
}


# package family
#

package_family_schema_dict = base_resource_schema_dict.copy()


# schema common to both package and variant
#

tests_schema = Schema({
    Optional(str): Or(
        Or(str, [str]),
        extensible_schema_dict({
            "command": Or(str, [str]),
            Optional("requires"): [
                Or(PackageRequest, And(str, Use(PackageRequest)))
            ],
            Optional("run_on"): Or(str, [str]),
            Optional("on_variants"): Or(
                bool,
                {
                    "type": "requires",
                    "value": [
                        Or(PackageRequest, And(str, Use(PackageRequest)))
                    ]
                }
            )
        })
    )
})

package_base_schema_dict = base_resource_schema_dict.copy()
package_base_schema_dict.update({
    # basics
    Optional("base"):                   str,
    Optional("version"):                Version,
    Optional('description'):            str,
    Optional('authors'):                [str],

    # dependencies
    Optional('requires'):               late_bound([PackageRequest]),
    Optional('build_requires'):         late_bound([PackageRequest]),
    Optional('private_build_requires'): late_bound([PackageRequest]),

    # plugins
    Optional('has_plugins'):            late_bound(bool),
    Optional('plugin_for'):             late_bound([str]),

    # general
    Optional('uuid'):                   str,
    Optional('config'):                 Config,
    Optional('tools'):                  late_bound([str]),
    Optional('help'):                   late_bound(help_schema),

    # build related
    Optional('hashed_variants'):        bool,

    # relocatability
    Optional('relocatable'):            late_bound(Or(None, bool)),
    Optional('cachable'):               late_bound(Or(None, bool)),

    # testing
    Optional('tests'):                  late_bound(tests_schema),

    # commands
    Optional('pre_commands'):           SourceCode,
    Optional('commands'):               SourceCode,
    Optional('post_commands'):          SourceCode,
    Optional('pre_build_commands'):     SourceCode,
    Optional('pre_test_commands'):      SourceCode,

    # release info
    Optional("timestamp"):              int,
    Optional('revision'):               object,
    Optional('changelog'):              str,
    Optional('release_message'):        Or(None, str),
    Optional('previous_version'):       Version,
    Optional('previous_revision'):      object,
    Optional('vcs'):                    str,

    # arbitrary fields
    Optional(str):               late_bound(object)
})


# package
package_schema_dict = package_base_schema_dict.copy()
package_schema_dict.update({
    # deliberately not possible to late bind
    Optional("variants"):               [[PackageRequest]]
})


# variant
variant_schema_dict = package_base_schema_dict.copy()


# ------------------------------------------------------------------------------
# resource schemas
# ------------------------------------------------------------------------------

package_family_schema = Schema(package_family_schema_dict)


package_schema = Schema(package_schema_dict)


variant_schema = Schema(variant_schema_dict)


# ------------------------------------------------------------------------------
# schemas for converting from POD datatypes
# ------------------------------------------------------------------------------

_commands_schema = Or(SourceCode,       # commands as converted function
                      callable,         # commands as function
                      str,       # commands in text block
                      [str])     # old-style (rez-1) commands

_function_schema = Or(SourceCode, callable)

_package_request_schema = And(str, Use(PackageRequest))

package_pod_schema_dict = base_resource_schema_dict.copy()

large_string_dict = And(str, Use(lambda x: dedent(x).strip()))


package_pod_schema_dict.update({
    Optional("base"):                   str,
    Optional("version"):                And(str, Use(Version)),
    Optional('description'):            large_string_dict,
    Optional('authors'):                [str],

    Optional('requires'):               late_bound([_package_request_schema]),
    Optional('build_requires'):         late_bound([_package_request_schema]),
    Optional('private_build_requires'): late_bound([_package_request_schema]),

    # deliberately not possible to late bind
    Optional('variants'):               [[_package_request_schema]],

    Optional('has_plugins'):            late_bound(bool),
    Optional('plugin_for'):             late_bound([str]),

    Optional('uuid'):                   str,
    Optional('config'):                 And(dict,
                                            Use(lambda x: create_config(overrides=x))),
    Optional('tools'):                  late_bound([str]),
    Optional('help'):                   late_bound(help_schema),

    Optional('hashed_variants'):        bool,

    Optional('relocatable'):            late_bound(Or(None, bool)),
    Optional('cachable'):               late_bound(Or(None, bool)),

    Optional('tests'):                  late_bound(tests_schema),

    Optional('pre_commands'):           _commands_schema,
    Optional('commands'):               _commands_schema,
    Optional('post_commands'):          _commands_schema,
    Optional('pre_build_commands'):     _commands_schema,
    Optional('pre_test_commands'):      _commands_schema,

    Optional("timestamp"):              int,
    Optional('revision'):               object,
    Optional('changelog'):              large_string_dict,
    Optional('release_message'):        Or(None, str),
    Optional('previous_version'):       And(str, Use(Version)),
    Optional('previous_revision'):      object,
    Optional('vcs'):                    str,

    # arbitrary keys
    Optional(str):               late_bound(object)
})


package_pod_schema = Schema(package_pod_schema_dict)


# ------------------------------------------------------------------------------
# resource classes
# ------------------------------------------------------------------------------

class PackageRepositoryResource(Resource):
    """Base class for all package-related resources.
    """
    schema_error = PackageMetadataError
    #: Type of package repository associated with this resource type.
    repository_type: str

    @classmethod
    def normalize_variables(cls, variables):
        if "repository_type" not in variables or "location" not in \
                variables:
            raise ResourceError("%s resources require a repository_type and "
                                "location" % cls.__name__)
        return super(PackageRepositoryResource, cls).normalize_variables(
            variables)

    def __init__(self, variables=None):
        super(PackageRepositoryResource, self).__init__(variables)

    @cached_property
    def uri(self) -> str:
        return self._uri()

    @property
    def location(self) -> str | None:
        return self.get("location")

    @property
    def name(self) -> str | None:
        return self.get("name")

    def _uri(self) -> str:
        """Return a URI.

        Implement this function to return a short, readable string that
        uniquely identifies this resource.
        """
        raise NotImplementedError


class PackageFamilyResource(PackageRepositoryResource):
    """A package family.

    A repository implementation's package family resource(s) must derive from
    this class. It must satisfy the schema `package_family_schema`.
    """

    def iter_packages(self) -> Iterator[PackageResourceHelper]:
        raise NotImplementedError


class PackageResource(PackageRepositoryResource):
    """A package.

    A repository implementation's package resource(s) must derive from this
    class. It must satisfy the schema `package_schema`.
    """

    @classmethod
    def normalize_variables(cls, variables):
        """Make sure version is treated consistently
        """
        # if the version is False, empty string, etc, throw it out
        if variables.get('version', True) in ('', False, '_NO_VERSION', None):
            del variables['version']
        return super(PackageResource, cls).normalize_variables(variables)

    @cached_property
    def version(self) -> Version:
        ver_str = self.get("version", "")
        return Version(ver_str)


class VariantResource(PackageResource):
    """A package variant.

    A repository implementation's variant resource(s) must derive from this
    class. It must satisfy the schema `variant_schema`.

    Even packages that do not have a 'variants' section contain a variant - in
    this case it is the 'None' variant (the value of `index` is None). This
    provides some internal consistency and simplifies the implementation.
    """

    @property
    @abstractmethod
    def parent(self) -> PackageRepositoryResource:
        raise NotImplementedError

    @property
    def index(self) -> int | None:
        return self.get("index", None)

    @cached_property
    def root(self) -> str:
        """Return the 'root' path of the variant."""
        return self._root()

    @cached_property
    def subpath(self) -> str:
        """Return the variant's 'subpath'

        The subpath is the relative path the variant's payload should be stored
        under, relative to the package base. If None, implies that the variant
        root matches the package base.
        """
        return self._subpath()

    @abstractmethod
    def _root(self, ignore_shortlinks=False):
        raise NotImplementedError

    @abstractmethod
    def _subpath(self, ignore_shortlinks=False):
        raise NotImplementedError


# ------------------------------------------------------------------------------
# resource helper classes
#
# Package repository plugins are not required to use the following classes, but
# they may help minimise the amount of code you need to write.
# ------------------------------------------------------------------------------

class PackageResourceHelper(PackageResource):
    """PackageResource with some common functionality included.
    """
    # the resource key for a VariantResourceHelper subclass
    variant_key: str

    if TYPE_CHECKING:
        # I think these attributes are provided dynamically be LazyAttributeMeta
        _commands: list[str] | str | FunctionType | MethodType | SourceCode
        _pre_commands: list[str] | str | FunctionType | MethodType | SourceCode
        _post_commands: list[str] | str | FunctionType | MethodType | SourceCode
        variants: list[Variant]

    @property
    @abstractmethod
    def base(self) -> str | None:
        raise NotImplementedError

    @property
    @abstractmethod
    def parent(self) -> PackageRepositoryResource:
        raise NotImplementedError

    @cached_property
    def commands(self) -> SourceCode:
        return self._convert_to_rex(self._commands)

    @cached_property
    def pre_commands(self) -> SourceCode:
        return self._convert_to_rex(self._pre_commands)

    @cached_property
    def post_commands(self) -> SourceCode:
        return self._convert_to_rex(self._post_commands)

    def iter_variants(self) -> Iterator[VariantResourceHelper]:
        num_variants = len(self.variants or [])

        if num_variants == 0:
            indexes: Iterable[int | None] = [None]
        else:
            indexes = range(num_variants)

        for index in indexes:
            variant = self._repository.get_resource(
                self.variant_key,
                location=self.location,
                name=self.name,
                version=self.get("version"),
                index=index)
            yield variant

    def _convert_to_rex(self, commands: list[str] | str | FunctionType | MethodType | SourceCode) -> SourceCode:
        if isinstance(commands, list):
            from rez.utils.backcompat import convert_old_commands

            msg = "package %r is using old-style commands." % self.uri
            if config.disable_rez_1_compatibility or config.error_old_commands:
                raise SchemaError(None, msg)
            elif config.warn("old_commands"):
                print_warning(msg)
            commands = convert_old_commands(commands)

        if isinstance(commands, str):
            return SourceCode(source=commands)
        elif callable(commands):
            return SourceCode(func=commands)
        else:
            return commands


class _Metas(AttributeForwardMeta, LazyAttributeMeta):
    pass


class VariantResourceHelper(VariantResource, metaclass=_Metas):
    """Helper class for implementing variants that inherit properties from their
    parent package.

    Since a variant overlaps so much with a package, here we use the forwarding
    metaclass to forward our parent package's attributes onto ourself (with some
    exceptions - eg 'variants', 'requires'). This is a common enough pattern
    that it's supplied here for other repository plugins to use.
    """

    # Note: lazy key validation doesn't happen in this class, it just fowards on
    # attributes from the package. But LazyAttributeMeta does still use this
    # schema to create other class attributes, such as `validate_data`.
    schema = variant_schema

    # forward Package attributes onto ourself
    keys = schema_keys(package_schema) - set(["variants"])

    def _uri(self) -> str:
        index = self.index
        idxstr = '' if index is None else str(index)
        return "%s[%s]" % (self.parent.uri, idxstr)

    def _subpath(self, ignore_shortlinks=False) -> str | None:
        if self.index is None:
            return None

        if self.parent.hashed_variants:
            vars_str = str(list(map(str, self.variant_requires)))
            h = sha1(vars_str.encode("utf8"))
            hashdir = h.hexdigest()

            if (not ignore_shortlinks) and \
                    config.use_variant_shortlinks and \
                    self.base is not None:

                # search for matching shortlink and use that
                path = os.path.join(self.base, config.variant_shortlinks_dirname)

                if os.path.exists(path):
                    actual_root = os.path.join(self.base, hashdir)
                    linkname = find_matching_symlink(path, actual_root)

                    if linkname:
                        return os.path.join(
                            config.variant_shortlinks_dirname, linkname)

            return hashdir
        else:
            dirs = [x.safe_str() for x in self.variant_requires]
            subpath = os.path.join(*dirs)
            return subpath

    def _root(self, ignore_shortlinks: bool = False) -> str | None:
        if self.base is None:
            return None
        elif self.index is None:
            return self.base
        else:
            subpath = self._subpath(ignore_shortlinks=ignore_shortlinks)
            root = os.path.join(self.base, subpath)
            return root

    @cached_property
    def variant_requires(self) -> list[Requirement]:
        index = self.index
        if index is None:
            return []
        else:
            try:
                return self.parent.variants[index] or []
            except (IndexError, TypeError):
                raise ResourceError(
                    "Unexpected error - variant %s cannot be found in its "
                    "parent package %s" % (self.uri, self.parent.uri))

    @property
    def wrapped(self):  # forward Package attributes onto ourself
        return self.parent

    def _load(self):
        # doesn't have its own data, forwards on from parent instead
        return None
