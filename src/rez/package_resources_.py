from rez.utils.resources import Resource
from rez.utils.schema import Required, schema_keys
from rez.utils.logging_ import print_warning
from rez.utils.data_utils import cached_property, SourceCode, \
    AttributeForwardMeta, LazyAttributeMeta
from rez.utils.formatting import PackageRequest
from rez.exceptions import PackageMetadataError
from rez.config import config, Config, create_config
from rez.vendor.version.version import Version
from rez.vendor.schema.schema import Schema, SchemaError, Optional, Or, And, Use
from textwrap import dedent
import os.path



# package attributes created at release time
package_release_keys = (
    "timestamp",
    'revision',
    'changelog',
    'release_message',
    'previous_version',
    'previous_revision')


#------------------------------------------------------------------------------
# utility schemas
#------------------------------------------------------------------------------

help_schema = Or(basestring,  # single help entry
                 [[basestring]])  # multiple help entries


#------------------------------------------------------------------------------
# schema dicts
#------------------------------------------------------------------------------

# requirements of all package-related resources
base_resource_schema_dict = {
    Required("name"):                   basestring
}


# package family
package_family_schema_dict = base_resource_schema_dict.copy()


# schema common to both package and variant
package_base_schema_dict = base_resource_schema_dict.copy()
package_base_schema_dict.update({
    # basics
    Optional("base"):                   basestring,
    Optional("version"):                Version,
    Optional('description'):            basestring,
    Optional('authors'):                [basestring],

    # dependencies
    Optional('requires'):               [PackageRequest],
    Optional('build_requires'):         [PackageRequest],
    Optional('private_build_requires'): [PackageRequest],

    # plugins
    Optional('has_plugins'):            bool,
    Optional('plugin_for'):             [basestring],

    # general
    Optional('uuid'):                   basestring,
    Optional('config'):                 Config,
    Optional('tools'):                  [basestring],
    Optional('help'):                   help_schema,

    # commands
    Optional('pre_commands'):           SourceCode,
    Optional('commands'):               SourceCode,
    Optional('post_commands'):          SourceCode,

    # release info
    Optional("timestamp"):              int,
    Optional('revision'):               object,
    Optional('changelog'):              basestring,
    Optional('release_message'):        Or(None, basestring),
    Optional('previous_version'):       Version,
    Optional('previous_revision'):      object,

    # custom keys
    Optional('custom'):                 dict
})


# package
package_schema_dict = package_base_schema_dict.copy()
package_schema_dict.update({
    Optional("variants"):               [[PackageRequest]]
})


# variant
variant_schema_dict = package_base_schema_dict.copy()


#------------------------------------------------------------------------------
# resource schemas
#------------------------------------------------------------------------------

package_family_schema = Schema(package_family_schema_dict)


package_schema = Schema(package_schema_dict)


variant_schema = Schema(variant_schema_dict)


#------------------------------------------------------------------------------
# schemas for converting from POD datatypes
#------------------------------------------------------------------------------

_commands_schema = Or(SourceCode,       # commands as converted function
                      callable,         # commands as function
                      basestring,       # commands in text block
                      [basestring])     # old-style (rez-1) commands


_package_request_schema = And(basestring, Use(PackageRequest))


package_pod_schema_dict = base_resource_schema_dict.copy()


large_string_dict = And(basestring, Use(lambda x: dedent(x).strip()))


package_pod_schema_dict.update({
    Optional("base"):                   basestring,
    Optional("version"):                And(basestring, Use(Version)),
    Optional('description'):            large_string_dict,
    Optional('authors'):                [basestring],

    Optional('requires'):               [_package_request_schema],
    Optional('build_requires'):         [_package_request_schema],
    Optional('private_build_requires'): [_package_request_schema],
    Optional('variants'):               [[_package_request_schema]],

    Optional('has_plugins'):            bool,
    Optional('plugin_for'):             [basestring],

    Optional('uuid'):                   basestring,
    Optional('config'):                 And(dict,
                                            Use(lambda x: create_config(overrides=x))),
    Optional('tools'):                  [basestring],
    Optional('help'):                   help_schema,

    Optional('pre_commands'):           _commands_schema,
    Optional('commands'):               _commands_schema,
    Optional('post_commands'):          _commands_schema,

    Optional("timestamp"):              int,
    Optional('revision'):               object,
    Optional('changelog'):              large_string_dict,
    Optional('release_message'):        Or(None, basestring),
    Optional('previous_version'):       And(basestring, Use(Version)),
    Optional('previous_revision'):      object,

    Optional('custom'):                 dict
})


package_pod_schema = Schema(package_pod_schema_dict)


#------------------------------------------------------------------------------
# resource classes
#------------------------------------------------------------------------------

class PackageRepositoryResource(Resource):
    """Base class for all package-related resources.

    Attributes:
        schema_error (`Exception`): Type of exception to throw on bad data.
        repository_type (str): Type of package repository associated with this
            resource type.
    """
    schema_error = PackageMetadataError
    repository_type = None

    def __init__(self, variables=None):
        super(PackageRepositoryResource, self).__init__(variables)
        self._repository = None

    @cached_property
    def uri(self):
        return self._uri()

    @property
    def location(self):
        return self.get("location")

    @property
    def name(self):
        return self.get("name")

    def _uri(self):
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
    pass


class PackageResource(PackageRepositoryResource):
    """A package.

    A repository implementation's package resource(s) must derive from this
    class. It must satisfy the schema `package_schema`.
    """
    @cached_property
    def version(self):
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
    def index(self):
        return self.get("index", None)

    @cached_property
    def root(self):
        """Return the 'root' path of the variant."""
        return self._root()

    @cached_property
    def subpath(self):
        """Return the variant's 'subpath'

        The subpath is the relative path the variant's payload should be stored
        under, relative to the package base. If None, implies that the variant
        root matches the package base.
        """
        return self._subpath()

    def _root(self):
        raise NotImplementedError

    def _subpath(self):
        raise NotImplementedError


#------------------------------------------------------------------------------
# resource helper classes
#
# Package repository plugins are not required to use the following classes, but
# they may help minimise the amount of code you need to write.
#------------------------------------------------------------------------------

class PackageResourceHelper(PackageResource):
    """PackageResource with some common functionality included.
    """
    variant_key = None

    @cached_property
    def commands(self):
        return self._convert_to_rex(self._commands)

    @cached_property
    def pre_commands(self):
        return self._convert_to_rex(self._pre_commands)

    @cached_property
    def post_commands(self):
        return self._convert_to_rex(self._post_commands)

    def iter_variants(self):
        num_variants = len(self._data.get("variants", []))
        if num_variants == 0:
            indexes = [None]
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

    def _convert_to_rex(self, commands):
        if isinstance(commands, list):
            from rez.utils.backcompat import convert_old_commands

            msg = "package %r is using old-style commands." % self.uri
            if config.disable_rez_1_compatibility or config.error_old_commands:
                raise SchemaError(None, msg)
            elif config.warn("old_commands"):
                print_warning(msg)
            commands = convert_old_commands(commands)

        if isinstance(commands, basestring):
            return SourceCode(commands)
        elif callable(commands):
            return SourceCode.from_function(commands)
        else:
            return commands


class VariantResourceHelper(VariantResource):
    """Helper class for implementing variants that inherit properties from their
    parent package.

    Since a variant overlaps so much with a package, here we use the forwarding
    metaclass to forward our parent package's attributes onto ourself (with some
    exceptions - eg 'variants', 'requires'). This is a common enough pattern
    that it's supplied here for other repository plugins to use.
    """
    class _Metas(AttributeForwardMeta, LazyAttributeMeta): pass
    __metaclass__ = _Metas

    # Note: lazy key validation doesn't happen in this class, it just fowards on
    # attributes from the package. But LazyAttributeMeta does still use this
    # schema to create other class attributes, such as `validate_data`.
    schema = variant_schema

    # forward Package attributes onto ourself
    keys = schema_keys(package_schema) - set(["requires", "variants"])

    def _uri(self):
        index = self.index
        idxstr = '' if index is None else str(index)
        return "%s[%s]" % (self.parent.uri, idxstr)

    def _subpath(self):
        if self.index is None:
            return None
        else:
            reqs = self.parent.variants[self.index]
            dirs = [x.safe_str() for x in reqs]
            subpath = os.path.join(*dirs)
            return subpath

    def _root(self):
        if self.base is None:
            return None
        elif self.index is None:
            return self.base
        else:
            root = os.path.join(self.base, self.subpath)
            return root

    @cached_property
    def requires(self):
        reqs = self.parent.requires or []
        index = self.index
        if index is not None:
            reqs = reqs + (self.parent.variants[index] or [])
        return reqs

    @property
    def wrapped(self):  # forward Package attributes onto ourself
        return self.parent

    def _load(self):
        # doesn't have its own data, forwards on from parent instead
        return None
