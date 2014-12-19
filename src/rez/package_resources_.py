from rez.utils.resources import Resource
from rez.utils.schema import Required
from rez.utils.data_utils import cached_property, SourceCode
from rez.utils.formatting import PackageRequest
from rez.exceptions import PackageMetadataError
from rez.config import Config
from rez.vendor.version.version import Version
from rez.vendor.schema.schema import Schema, Optional, Or


#------------------------------------------------------------------------------
# type schemas
#------------------------------------------------------------------------------

#commands_schema = Or(callable,  # commands function
#                     basestring)  # commands in text block


help_schema = Or(basestring,  # single help entry
                 [[basestring]])  # multiple help entries


#------------------------------------------------------------------------------
# schema dicts
#------------------------------------------------------------------------------

# requirements of all package-related resources
base_resource_schema_dict = {
    Required("repository_type"):        basestring,
    Required("location"):               basestring,
    Required("uri"):                    basestring,
    Required("name"):                   basestring
}


# package family
package_family_schema_dict = base_resource_schema_dict.copy()


# schema common to both package and variant
package_base_schema_dict = base_resource_schema_dict.copy()
package_base_schema_dict.update({
    # basics
    Required("base"):                   basestring,
    Optional("version"):                Version,
    Optional('description'):            basestring,
    Optional('authors'):                [basestring],

    # dependencies
    Optional('requires'):               [PackageRequest],
    Optional('build_requires'):         [PackageRequest],
    Optional('private_build_requires'): [PackageRequest],

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
    Optional("variants"):            [[PackageRequest]]
})


# variant
variant_schema_dict = package_base_schema_dict.copy()
variant_schema_dict.update({
    Required("root"):                   basestring,
    Optional("index"):                  int,
})


#------------------------------------------------------------------------------
# resource schemas
#------------------------------------------------------------------------------

package_family_schema = Schema(package_family_schema_dict)


package_schema = Schema(package_schema_dict)


variant_schema = Schema(variant_schema_dict)


#------------------------------------------------------------------------------
# resource classes
#------------------------------------------------------------------------------

class PackageRepositoryResource(Resource):
    """Base class for all package-related resources.

    Attributes:
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
