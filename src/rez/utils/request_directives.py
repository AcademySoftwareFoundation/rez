
from rez.vendor.six import six
from rez.vendor.schema.schema import Schema, Optional, Use, And
from rez.package_resources import late_bound
from rez.utils.formatting import PackageRequest
from rez.exceptions import PackageMetadataError


basestring = six.string_types[0]


def filter_directive_requires(data):
    """Filtering raw developer package data with directive extracted

    Args:
        data (`dict`): Package data that is not yet been validated

    Returns:
        validated (`dict`): filtered package data
        directives (`dict`): request-name, directive object paired dict
    """
    _directives = dict()

    def extract_directive(request):
        for Directive in _directive_classes:
            directive = Directive.create(request)
            if directive is not None:
                break
        else:
            # not a directive request
            return request

        request_ = directive.get_pre_build_request()
        _directives[request_.name] = directive

        return str(request_)

    # visit requires with schema
    #
    filtering_schema = And(basestring, Use(extract_directive))

    requires_filtering_schema = Schema({
        Optional("requires"):               late_bound([filtering_schema]),
        Optional("build_requires"):         late_bound([filtering_schema]),
        Optional("private_build_requires"): late_bound([filtering_schema]),
        Optional("variants"):               [[filtering_schema]],
    })

    validated = _validate_partial(requires_filtering_schema, data)

    return validated, _directives


def expand_directive_requires(data, directives, build_context, variant_index):
    """Expand directive request with build resolved context

    Args:
        data (`dict`): Package validated data
        directives (`dict`): request-name, directive object paired dict
        build_context (`ResolvedContext`): A context resolved for build
        variant_index (None or `int`): Variant index

    Returns:
        validated (`dict`): evaluated package data
    """

    def expand_directive(request):
        directive = directives.get(request.name)
        if directive:
            request = directive.get_post_build_request(build_context)
        return request

    expansion_schema = And(PackageRequest, Use(expand_directive))

    requires_expansion_schema = Schema({
        Optional("requires"):               [expansion_schema],
        Optional("build_requires"):         [expansion_schema],
        Optional("private_build_requires"): [expansion_schema],
        Optional("variants"):               [[expansion_schema]],
    })

    validated = _validate_partial(requires_expansion_schema, data)

    if variant_index is not None and "variants" in validated:
        # for example:
        #   variants = [["foo-1"], ["foo-2"]]
        # both variant required "foo" will get harden into same version,
        # owning to schema validation could not know which variant it's
        # validating, so we need to restore original value for other variant.
        variants = data["variants"][:]
        variants[variant_index] = validated["variants"][variant_index]
        validated["variants"] = variants

    return validated


def _validate_partial(schema, data):
    s = schema._schema
    partial_data = dict()

    for key in s:
        key_name = key
        while isinstance(key_name, Schema):
            key_name = key_name._schema
        if isinstance(key_name, str):
            value = data.get(key_name)
            if value is not None:
                partial_data[key_name] = value

    return schema.validate(partial_data)


# directives
#

class DirectiveBase(object):
    """Base class of directive request handler"""

    def __init__(self, request_str, raw_request_str=None):
        self._raw_request_str = raw_request_str
        self._request = PackageRequest(request_str)

    @classmethod
    def name(cls):
        return None

    @classmethod
    def create(cls, request):
        raise NotImplementedError

    def get_raw_request_string(self):
        return self._raw_request_str

    def get_pre_build_request(self):
        return self._request

    def get_post_build_request(self, build_context):
        raise NotImplementedError


class HardenDirective(DirectiveBase):
    """Harden directive request version to specific rank"""

    def __init__(self, request_str, raw_request_str=None, rank=None):
        super(HardenDirective, self).__init__(request_str, raw_request_str)
        self._can_harden_request()
        self.rank = rank

    @classmethod
    def name(cls):
        return "harden"

    @classmethod
    def create(cls, request_str):
        if "//" not in request_str:
            return

        request_, d_str = request_str.split("//", 1)
        rank = None
        name = cls.name()

        if d_str == name or d_str.startswith(name + "("):

            arg_str = d_str[len(name):]
            if arg_str:
                rank = int(arg_str[1:-1].strip())

            return cls(request_, request_str, rank=rank)

    def _can_harden_request(self):
        if self._request.conflict:
            raise PackageMetadataError("Cannot harden conflict request.")

    def get_post_build_request(self, build_context):
        pkg_name = self._request.name
        variant = build_context.get_resolved_package(pkg_name)

        if variant is None:
            # this may happen when requires is early bound and requested
            # package is not in build requires, e.g.
            #
            #   @early()
            #   def requires():
            #       return [] if building else ["foo-1//harden"]
            #
            return self._request

        else:
            version = variant.version
            if self.rank is not None:
                version = version.trim(self.rank)

            request_str = "%s-%s" % (pkg_name, version)
            return PackageRequest(request_str)


_directive_classes = (
    HardenDirective,
)
