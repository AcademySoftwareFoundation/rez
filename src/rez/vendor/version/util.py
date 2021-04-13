
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


def is_valid_bound(bound):
    """"""
    lower_tokens = bound.lower.version.tokens
    upper_tokens = bound.upper.version.tokens
    return ((lower_tokens is None or lower_tokens)
            or (upper_tokens is None or upper_tokens))


def fix_bound(bound):
    lower_tokens = bound.lower.version.tokens
    if not lower_tokens:
        bound.lower = bound.lower.min
    upper_tokens = bound.upper.version.tokens
    if not upper_tokens:
        bound.upper = bound.upper.inf


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
        from .version import VersionRange

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

        for bound in list(req.range_.bounds):
            if is_valid_bound(bound):
                fix_bound(bound)
            else:
                req.range_.bounds.remove(bound)

        if not req.range_.bounds:
            req.range_ = VersionRange()
