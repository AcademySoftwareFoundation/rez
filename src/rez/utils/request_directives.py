
from rez.vendor.schema.schema import Schema, Optional, Use, And
from rez.vendor.version.version import VersionRange
from rez.vendor.version.requirement import Requirement
from rez.vendor.version.util import dewildcard
from rez.utils.formatting import PackageRequest
from copy import copy
import inspect
import sys


# directives
#

class DirectiveBase(object):
    """Base class of directive request handler"""
    @classmethod
    def name(cls):
        """Return the name of the directive"""
        raise NotImplementedError

    def parse(self, arg_string):
        """Parse arguments from directive syntax string"""
        raise NotImplementedError

    def to_string(self, args):
        """Format arguments to directive syntax string"""
        raise NotImplementedError

    def process(self, range_, version, rank=None):
        """Process requirement's version range"""
        raise NotImplementedError


class DirectiveHarden(DirectiveBase):
    """Harden directive request version to specific rank"""
    @classmethod
    def name(cls):
        return "harden"

    def parse(self, arg_string):
        if arg_string:
            return [int(arg_string[1:-1].strip())]
        return []

    def to_string(self, args):
        if args and args[0]:
            return "%s(%d)" % (self.name(), args[0])
        return self.name()

    def process(self, range_, version, rank=None):
        if rank:
            version = version.trim(rank)
        hardened = VersionRange.from_version(version)
        new_range = range_.intersection(hardened)
        return new_range


# helpers
#

def parse_directive(request):
    """Parsing directive requests when creating package
    """
    if "//" in request:
        request_, directive = request.split("//", 1)
    elif "*" in request:
        request_, directive = _convert_wildcard_to_directive(request)
        if not directive:
            return request
    else:
        return request

    # parse directive and save into anonymous inventory
    _directive_args = directive_manager.parse(directive)
    directive_manager.loaded.put(_directive_args,
                                 key=request_,
                                 anonymous=True)

    return request_


def _convert_wildcard_to_directive(request):
    ranks = dict()

    with dewildcard(request) as deer:
        req = deer.victim

        def ranking(version, rank_):
            wild_ver = deer.restore(str(version))
            ranks[wild_ver] = rank_
        deer.on_version(ranking)

    cleaned_request = str(req)
    # do some cleanup
    cleaned_request = deer.restore(cleaned_request)

    if len(ranks) > 1:
        # should we support this ?
        return None, None
    else:
        rank = next(iter(ranks.values()))

        if rank < 0:
            directive = "harden"
        else:
            directive = "harden(%d)" % rank

        return cleaned_request, directive


def bind_directives(package):
    """Bind previously parsed directives to each variants
    """
    anonymous = directive_manager.loaded.storage(anonymous=True)

    for variant in package.iter_variants():
        requires = copy(variant.variant_requires)
        requires += variant.get_requires(build_requires=True,
                                         private_build_requires=True)
        requires_str = set(map(str, requires))

        data = {r: v for r, v in anonymous.items() if r in requires_str}
        directive_manager.loaded.put(data, key=variant)

    directive_manager.loaded.clear(anonymous=True)


def process_directives(variant, context):
    """Evaluate directives with resolved context
    """
    package = variant.parent
    package_data = package.validated_data()

    directives = directive_manager.loaded.retrieve(key=variant) or dict()
    resolved_packages = {p.name: p for p in context.resolved_packages}

    processed = dict()
    directed = list()

    def visit_directive(request):
        directive_name, args = directives.get(str(request)) or (None, None)
        resolved = resolved_packages.get(request.name)

        if directive_name and resolved:
            request = PackageRequest(str(
                Requirement.construct(
                    name=resolved.name,
                    range=directive_manager.process(
                        request.range, resolved.version, directive_name, args,
                    ))
            ))
            directed.append(request)

        return request

    visitor = And(PackageRequest, Use(visit_directive))
    schemas = {
        "requires": [visitor],
        "build_requires": [visitor],
        "private_build_requires": [visitor],
        "variants": [[visitor]],
    }

    for key, value in schemas.items():
        if key not in package_data:
            continue
        schema = Schema({Optional(key): value})
        data = schema.validate({key: package_data[key]})
        if directed:
            processed[key] = copy(data[key])
            directed.clear()

    directive_manager.processed.put(processed, key=variant)


def apply_directives(variant):
    """Patch evaluated directives to variant on install
    """
    directed_requires = directive_manager.processed.retrieve(key=variant)

    # Just like how `cached_property` caching attributes, override
    # requirement attributes internally. These change will be picked
    # up by `variant.parent.validated_data`.
    for key, value in directed_requires.items():
        setattr(variant.parent.resource, key, value)
        if key == "variants":
            setattr(variant.resource, "variant_requires", value[variant.index])


class DirectiveManager(object):

    def __init__(self):
        self._loaded = VariantDataInventory()
        self._processed = VariantDataInventory()
        self._handlers = dict()

    @property
    def loaded(self):
        return self._loaded

    @property
    def processed(self):
        return self._processed

    def register_handler(self, cls, name=None, *args, **kwargs):
        name = name or cls.name()
        self._handlers[name] = cls(*args, **kwargs)

    def parse(self, string):
        for name, handler in self._handlers.items():
            if string == name or string.startswith(name + "("):
                return name, handler.parse(string[len(name):])

    def to_string(self, name, args):
        handler = self._handlers[name]
        return handler.to_string(args)

    def process(self, range_, version, name, args):
        handler = self._handlers[name]
        return handler.process(range_, version, *args)


class VariantDataInventory(object):

    def __init__(self):
        self._anonymous = dict()
        self._identified = dict()

    def _hash(self, key, anonymous):
        if anonymous:
            return key
        else:
            variant = key
            return (
                variant.name,
                str(variant.version),
                variant.uuid,
                variant.index,
            )

    def storage(self, anonymous):
        return self._anonymous if anonymous else self._identified

    def put(self, data, key, anonymous=False):
        key = self._hash(key, anonymous)
        storage = self.storage(anonymous)
        storage[key] = data

    def retrieve(self, key, anonymous=False):
        key = self._hash(key, anonymous)
        storage = self.storage(anonymous)
        if key in storage:
            return copy(storage[key])

    def drop(self, key, anonymous=False):
        key = self._hash(key, anonymous)
        storage = self.storage(anonymous)
        if key in storage:
            storage.pop(key)

    def clear(self, anonymous=False):
        storage = self.storage(anonymous)
        storage.clear()


def anonymous_directive_string(request):
    """Test use"""
    name, args = directive_manager.loaded.retrieve(request, anonymous=True)
    return directive_manager.to_string(name, args)


directive_manager = DirectiveManager()

# Auto register all subclasses of DirectiveBase in this module
for obj in list(sys.modules[__name__].__dict__.values()):
    if not inspect.isclass(obj):
        continue
    if issubclass(obj, DirectiveBase) and obj is not DirectiveBase:
        directive_manager.register_handler(obj)
