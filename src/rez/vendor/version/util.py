
from contextlib import contextmanager
from itertools import groupby
from uuid import uuid4


class VersionError(Exception):
    pass


class ParseException(Exception):
    pass


class _Common(object):
    def __str__(self):
        raise NotImplementedError

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, str(self))


def dedup(iterable):
    """Removes duplicates from a sorted sequence."""
    for e in groupby(iterable):
        yield e[0]


@contextmanager
def dewildcard(request):
    deer = WildcardReplacer(request)
    yield deer
    deer.clean()


class WildcardReplacer(object):

    def __init__(self, request):
        from .requirement import Requirement

        self.wildcard_map = dict()
        self._req = None
        self._on_wildcard = None
        self._on_version = None

        # replace wildcards with valid version tokens that can be replaced again
        # afterwards. This produces a horrendous, but both valid and temporary,
        # version string.
        #
        while "**" in request:
            uid = "_%s_" % uuid4().hex
            request = request.replace("**", uid, 1)
            self.wildcard_map[uid] = "**"

        while "*" in request:
            uid = "_%s_" % uuid4().hex
            request = request.replace("*", uid, 1)
            self.wildcard_map[uid] = "*"

        self._req = Requirement(request, invalid_bound_error=False)

    @property
    def victim(self):
        return self._req

    def on_wildcard(self, func):
        self._on_wildcard = func

    def on_version(self, func):
        self._on_version = func

    def restore(self, string):
        for uid, token in self.wildcard_map.items():
            string = string.replace(uid, token)
        return string

    def clean(self, on_wildcard=None, on_version=None):
        on_wildcard = on_wildcard or self._on_wildcard or (lambda v, r: v)
        on_version = on_version or self._on_version or (lambda v, r: None)

        req = self._req
        wildcard_map = self.wildcard_map
        cleaned_versions = dict()

        def clean_version(version):
            rank = len(version)
            original = version
            wildcard_found = False

            while version and str(version[-1]) in wildcard_map:
                token_ = wildcard_map[str(version[-1])]
                version = version.trim(len(version) - 1)

                if token_ == "**":
                    if wildcard_found:  # catches bad syntax '**.*'
                        return None
                    else:
                        wildcard_found = True
                        rank = 0
                        break

                wildcard_found = True

            on_version(original, rank)
            if wildcard_found:
                return on_wildcard(version, rank)

        def visit_version(version):
            # requirements like 'foo-1' are actually represented internally as
            # 'foo-1+<1_' - '1_' is the next possible version after '1'. So we have
            # to detect this case and remap the uid-ified wildcard back here too.
            #
            for v, expanded_v in cleaned_versions.items():
                if version == next(v):
                    return next(expanded_v)

            version_ = clean_version(version)
            if version_ is None:
                return None

            cleaned_versions[version] = version_
            return version_

        req.range_.visit_versions(visit_version)
        ensure_valid_range_bounds(req)


def ensure_valid_range_bounds(requirement):
    """Ensure requirement has no broken bounds after wildcard cleanup"""
    from .version import VersionRange

    for bound in list(requirement.range_.bounds):
        lower_tokens = bound.lower.version.tokens
        upper_tokens = bound.upper.version.tokens

        if ((lower_tokens is None or lower_tokens)
                or (upper_tokens is None or upper_tokens)):

            if not lower_tokens:
                bound.lower = bound.lower.min
            if not upper_tokens:
                bound.upper = bound.upper.inf

        else:
            # invalid bound
            requirement.range_.bounds.remove(bound)

    if not requirement.range_.bounds:
        requirement.range_ = VersionRange()
