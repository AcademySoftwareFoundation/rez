"""
Implements a well defined versioning schema.

There are three class types - VersionToken, Version and VersionRange. A Version
is a set of zero or more VersionTokens, separate by '.'s or '-'s (eg "1.2-3").
A VersionToken is a string containing alphanumerics, and default implemenations
'NumericToken' and 'AlphanumericVersionToken' are supplied. You can implement
your own if you want stricter tokens or different sorting behaviour.

A VersionRange is a set of one or more contiguous version ranges - for example,
"3+<5" contains any version >=3 but less than 5. Version ranges can be used to
define dependency requirements between objects. They can be OR'd together, AND'd
and inverted.

The empty version '', and empty version range '', are also handled. The empty
version is used to denote unversioned objects. The empty version range, also
known as the 'any' range, is used to refer to any version of an object.
"""
from __future__ import print_function
from .util import VersionError, ParseException, _Common, \
    dedup
import rez.vendor.pyparsing.pyparsing as pp
from bisect import bisect_left
import copy
import string
import re


re_token = re.compile(r"[a-zA-Z0-9_]+")


class _Comparable(_Common):
    def __gt__(self, other):
        return not (self < other or self == other)

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return not self < other


class _ReversedComparable(_Common):
    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return not (self.value < other.value)

    def __gt__(self, other):
        return not (self < other or self == other)

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return not self < other

    def __str__(self):
        return "reverse(%s)" % str(self.value)

    def __repr__(self):
        return "reverse(%r)" % self.value


class VersionToken(_Comparable):
    """Token within a version number.

    A version token is that part of a version number that appears between a
    delimiter, typically '.' or '-'. For example, the version number '2.3.07b'
    contains the tokens '2', '3' and '07b' respectively.

    Version tokens are only allowed to contain alphanumerics (any case) and
    underscores.
    """
    def __init__(self, token):
        """Create a VersionToken.

        Args:
            token: Token string, eg "rc02"
        """
        raise NotImplementedError

    @classmethod
    def create_random_token_string(cls):
        """Create a random token string. For testing purposes only."""
        raise NotImplementedError

    def less_than(self, other):
        """Compare to another VersionToken.

        Args:
            other: The VersionToken object to compare against.

        Returns:
            True if this token is less than other, False otherwise.
        """
        raise NotImplementedError

    def next(self):
        """Returns the next largest token."""
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError

    def __lt__(self, other):
        return self.less_than(other)

    def __eq__(self, other):
        return (not self < other) and (not other < self)


class NumericToken(VersionToken):
    """Numeric version token.

    Version token supporting numbers only. Padding is ignored.
    """
    def __init__(self, token):
        if not token.isdigit():
            raise VersionError("Invalid version token: '%s'" % token)
        else:
            self.n = int(token)

    @classmethod
    def create_random_token_string(cls):
        import random
        chars = string.digits
        return ''.join([chars[random.randint(0, len(chars) - 1)]
                       for _ in range(8)])

    def __str__(self):
        return str(self.n)

    def __eq__(self, other):
        return (self.n == other.n)

    def less_than(self, other):
        return (self.n < other.n)

    def __next__(self):
        other = copy.copy(self)
        other.n = self.n = 1
        return other

    def next(self):
        return self.__next__()


class _SubToken(_Comparable):
    """Used internally by AlphanumericVersionToken."""
    def __init__(self, s):
        self.s = s
        self.n = int(s) if s.isdigit() else None

    def __lt__(self, other):
        if self.n is None:
            return (self.s < other.s) if other.n is None else True
        else:
            return False if other.n is None \
                else ((self.n, self.s) < (other.n, other.s))

    def __eq__(self, other):
        return (self.s == other.s) and (self.n == other.n)

    def __str__(self):
        return self.s


class AlphanumericVersionToken(VersionToken):
    """Alphanumeric version token.

    These tokens compare as follows:
    - each token is split into alpha and numeric groups (subtokens);
    - the resulting subtoken list is compared.
    - alpha comparison is case-sensitive, numeric comparison is padding-sensitive.

    Subtokens compare as follows:
    - alphas come before numbers;
    - alphas are compared alphabetically (_, then A-Z, then a-z);
    - numbers are compared numerically. If numbers are equivalent but zero-
      padded differently, they are then compared alphabetically. Thus "01" < "1".

    Some example comparisons that equate to true:
    - "3" < "4"
    - "01" < "1"
    - "beta" < "1"
    - "alpha3" < "alpha4"
    - "alpha" < "alpha3"
    - "gamma33" < "33gamma"
    """
    numeric_regex = re.compile("[0-9]+")
    regex = re.compile(r"[a-zA-Z0-9_]+\Z")

    def __init__(self, token):
        if token is None:
            self.subtokens = None
        elif not self.regex.match(token):
            raise VersionError("Invalid version token: '%s'" % token)
        else:
            self.subtokens = self._parse(token)

    @classmethod
    def create_random_token_string(cls):
        import random
        chars = string.digits + string.ascii_letters
        return ''.join([chars[random.randint(0, len(chars) - 1)]
                       for _ in range(8)])

    def __str__(self):
        return ''.join(map(str, self.subtokens))

    def __eq__(self, other):
        return (self.subtokens == other.subtokens)

    def less_than(self, other):
        return (self.subtokens < other.subtokens)

    def __next__(self):
        other = AlphanumericVersionToken(None)
        other.subtokens = self.subtokens[:]
        subtok = other.subtokens[-1]
        if subtok.n is None:
            other.subtokens[-1] = _SubToken(subtok.s + '_')
        else:
            other.subtokens.append(_SubToken('_'))
        return other

    def next(self):
        return self.__next__()

    @classmethod
    def _parse(cls, s):
        subtokens = []
        alphas = cls.numeric_regex.split(s)
        numerics = cls.numeric_regex.findall(s)
        b = True

        while alphas or numerics:
            if b:
                alpha = alphas[0]
                alphas = alphas[1:]
                if alpha:
                    subtokens.append(_SubToken(alpha))
            else:
                numeric = numerics[0]
                numerics = numerics[1:]
                subtokens.append(_SubToken(numeric))
            b = not b

        return subtokens


def reverse_sort_key(comparable):
    """Key that gives reverse sort order on versions and version ranges.

    Example:

        >>> Version("1.0") < Version("2.0")
        True
        >>> reverse_sort_key(Version("1.0")) < reverse_sort_key(Version("2.0"))
        False

    Args:
        comparable (`Version` or `VesionRange`): Object to wrap.

    Returns:
        `_ReversedComparable`: Wrapper object that reverses comparisons.
    """
    return _ReversedComparable(comparable)


class Version(_Comparable):
    """Version object.

    A Version is a sequence of zero or more version tokens, separated by either
    a dot '.' or hyphen '-' delimiters. Note that separators only affect Version
    objects cosmetically - in other words, the version '1.0.0' is equivalent to
    '1-0-0'.

    The empty version '' is the smallest possible version, and can be used to
    represent an unversioned resource.
    """
    inf = None

    def __init__(self, ver_str='', make_token=AlphanumericVersionToken):
        """Create a Version object.

        Args:
            ver_str: Version string.
            make_token: Callable that creates a VersionToken subclass from a
                string.
        """
        self.tokens = []
        self.seps = []
        self._str = None
        self._hash = None

        if ver_str:
            toks = re_token.findall(ver_str)
            if not toks:
                raise VersionError(ver_str)

            seps = re_token.split(ver_str)
            if seps[0] or seps[-1] or max(len(x) for x in seps) > 1:
                raise VersionError("Invalid version syntax: '%s'" % ver_str)

            for tok in toks:
                try:
                    self.tokens.append(make_token(tok))
                except VersionError as e:
                    raise VersionError("Invalid version '%s': %s"
                                       % (ver_str, str(e)))

            self.seps = seps[1:-1]

    def copy(self):
        """Returns a copy of the version."""
        other = Version(None)
        other.tokens = self.tokens[:]
        other.seps = self.seps[:]
        return other

    def trim(self, len_):
        """Return a copy of the version, possibly with less tokens.

        Args:
            len_ (int): New version length. If >= current length, an
                unchanged copy of the version is returned.
        """
        other = Version(None)
        other.tokens = self.tokens[:len_]
        other.seps = self.seps[:len_ - 1]
        return other

    def __next__(self):
        """Return 'next' version. Eg, next(1.2) is 1.2_"""
        if self.tokens:
            other = self.copy()
            tok = other.tokens.pop()
            other.tokens.append(tok.next())
            return other
        else:
            return Version.inf

    def next(self):
        return self.__next__()

    @property
    def major(self):
        """Semantic versioning major version."""
        return self[0]

    @property
    def minor(self):
        """Semantic versioning minor version."""
        return self[1]

    @property
    def patch(self):
        """Semantic versioning patch version."""
        return self[2]

    def as_tuple(self):
        """Convert to a tuple of strings.

        Example:

            >>> print Version("1.2.12").as_tuple()
            ('1', '2', '12')
        """
        return tuple(map(str, self.tokens))

    def __len__(self):
        return len(self.tokens or [])

    def __getitem__(self, index):
        try:
            return (self.tokens or [])[index]
        except IndexError:
            raise IndexError("version token index out of range")

    def __nonzero__(self):
        """The empty version equates to False."""
        return bool(self.tokens)

    __bool__ = __nonzero__  # py3 compat

    def __eq__(self, other):
        return isinstance(other, Version) and self.tokens == other.tokens

    def __lt__(self, other):
        if self.tokens is None:
            return False
        elif other.tokens is None:
            return True
        else:
            return (self.tokens < other.tokens)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(None) if self.tokens is None \
                else hash(tuple(map(str, self.tokens)))
        return self._hash

    def __str__(self):
        if self._str is None:
            self._str = "[INF]" if self.tokens is None \
                else ''.join(str(x) + y for x, y in zip(self.tokens, self.seps + ['']))
        return self._str


# internal use only
Version.inf = Version()
Version.inf.tokens = None


class _LowerBound(_Comparable):
    min = None

    def __init__(self, version, inclusive):
        self.version = version
        self.inclusive = inclusive

    def __str__(self):
        if self.version:
            s = "%s+" if self.inclusive else ">%s"
            return s % self.version
        else:
            return '' if self.inclusive else ">"

    def __eq__(self, other):
        return (self.version == other.version) \
            and (self.inclusive == other.inclusive)

    def __lt__(self, other):
        return (self.version < other.version) \
            or ((self.version == other.version)
                and (self.inclusive and not other.inclusive))

    def __hash__(self):
        return hash((self.version, self.inclusive))

    def contains_version(self, version):
        return (version > self.version) \
            or (self.inclusive and (version == self.version))

_LowerBound.min = _LowerBound(Version(), True)


class _UpperBound(_Comparable):
    inf = None

    def __init__(self, version, inclusive):
        self.version = version
        self.inclusive = inclusive
        if not version and not inclusive:
            raise VersionError("Invalid upper bound: '%s'" % str(self))

    def __str__(self):
        s = "<=%s" if self.inclusive else "<%s"
        return s % self.version

    def __eq__(self, other):
        return (self.version == other.version) \
            and (self.inclusive == other.inclusive)

    def __lt__(self, other):
        return (self.version < other.version) \
            or ((self.version == other.version)
                and (not self.inclusive and other.inclusive))

    def __hash__(self):
        return hash((self.version, self.inclusive))

    def contains_version(self, version):
        return (version < self.version) \
            or (self.inclusive and (version == self.version))

_UpperBound.inf = _UpperBound(Version.inf, True)


class _Bound(_Comparable):
    any = None

    def __init__(self, lower=None, upper=None, invalid_bound_error=True):
        self.lower = lower or _LowerBound.min
        self.upper = upper or _UpperBound.inf

        if (invalid_bound_error and
            (self.lower.version > self.upper.version
             or ((self.lower.version == self.upper.version)
                 and not (self.lower.inclusive and self.upper.inclusive)))):
            raise VersionError("Invalid bound")

    def __str__(self):
        if self.upper.version == Version.inf:
            return str(self.lower)
        elif self.lower.version == self.upper.version:
            return "==%s" % str(self.lower.version)
        elif self.lower.inclusive and self.upper.inclusive:
            if self.lower.version:
                return "%s..%s" % (self.lower.version, self.upper.version)
            else:
                return "<=%s" % self.upper.version
        elif (self.lower.inclusive and not self.upper.inclusive) \
                and (self.lower.version.next() == self.upper.version):
            return str(self.lower.version)
        else:
            return "%s%s" % (self.lower, self.upper)

    def __eq__(self, other):
        return (self.lower == other.lower) and (self.upper == other.upper)

    def __lt__(self, other):
        return (self.lower, self.upper) < (other.lower, other.upper)

    def __hash__(self):
        return hash((self.lower, self.upper))

    def lower_bounded(self):
        return (self.lower != _LowerBound.min)

    def upper_bounded(self):
        return (self.upper != _UpperBound.inf)

    def contains_version(self, version):
        return (self.version_containment(version) == 0)

    def version_containment(self, version):
        if not self.lower.contains_version(version):
            return -1
        if not self.upper.contains_version(version):
            return 1
        return 0

    def contains_bound(self, bound):
        return (self.lower <= bound.lower) and (self.upper >= bound.upper)

    def intersects(self, other):
        lower = max(self.lower, other.lower)
        upper = min(self.upper, other.upper)

        return (lower.version < upper.version) or \
            ((lower.version == upper.version) and
             (lower.inclusive and upper.inclusive))

    def intersection(self, other):
        lower = max(self.lower, other.lower)
        upper = min(self.upper, other.upper)

        if (lower.version < upper.version) or \
            ((lower.version == upper.version) and
             (lower.inclusive and upper.inclusive)):
            return _Bound(lower, upper)
        else:
            return None

_Bound.any = _Bound()


class _VersionRangeParser(object):
    debug = False  # set to True to enable parser debugging

    re_flags = (re.VERBOSE | re.DEBUG) if debug else re.VERBOSE

    # The regular expression for a version - one or more version tokens
    # followed by a non-capturing group of version separator followed by
    # one or more version tokens.
    #
    # Note that this assumes AlphanumericVersionToken-based versions!
    #
    # TODO - Would be better to have `VersionRange` keep a static dict of
    # parser instances, per token class type. We would add a 'regex' static
    # string to each token class, and that could be used to construct
    # `version_group` as below. We need to keep a dict of these parser instances,
    # to avoid recompiling the large regex every time a version range is
    # instantiated. In the cpp port this would be simpler - VersionRange could
    # just have a static parser that is instantiated when the version range
    # template class is instantiated.
    #
    version_group = r"([0-9a-zA-Z_]+(?:[.-][0-9a-zA-Z_]+)*)"

    version_range_regex = (
        # Match a version number (e.g. 1.0.0)
        r"   ^(?P<version>{version_group})$"
        "|"
        # Or match an exact version number (e.g. ==1.0.0)
        "    ^(?P<exact_version>"
        "        =="  # Required == operator
        "        (?P<exact_version_group>{version_group})?"
        "    )$"
        "|"
        # Or match an inclusive bound (e.g. 1.0.0..2.0.0)
        "    ^(?P<inclusive_bound>"
        "        (?P<inclusive_lower_version>{version_group})?"
        "        \.\."  # Required .. operator
        "        (?P<inclusive_upper_version>{version_group})?"
        "    )$"
        "|"
        # Or match a lower bound (e.g. 1.0.0+)
        "    ^(?P<lower_bound>"
        "        (?P<lower_bound_prefix>>|>=)?"  # Bound is exclusive?
        "        (?P<lower_version>{version_group})?"
        "        (?(lower_bound_prefix)|\+)"  # + only if bound is not exclusive
        "    )$"
        "|"
        # Or match an upper bound (e.g. <=1.0.0)
        "    ^(?P<upper_bound>"
        "        (?P<upper_bound_prefix><(?={version_group})|<=)?"  # Bound is exclusive?
        "        (?P<upper_version>{version_group})?"
        "    )$"
        "|"
        # Or match a range in ascending order (e.g. 1.0.0+<2.0.0)
        "    ^(?P<range_asc>"
        "        (?P<range_lower_asc>"
        "           (?P<range_lower_asc_prefix>>|>=)?"  # Lower bound is exclusive?
        "           (?P<range_lower_asc_version>{version_group})?"
        "           (?(range_lower_asc_prefix)|\+)?"  # + only if lower bound is not exclusive
        "       )(?P<range_upper_asc>"
        "           (?(range_lower_asc_version),?|)"  # , only if lower bound is found
        "           (?P<range_upper_asc_prefix><(?={version_group})|<=)"  # <= only if followed by a version group
        "           (?P<range_upper_asc_version>{version_group})?"
        "       )"
        "    )$"
        "|"
        # Or match a range in descending order (e.g. <=2.0.0,1.0.0+)
        "    ^(?P<range_desc>"
        "        (?P<range_upper_desc>"
        "           (?P<range_upper_desc_prefix><|<=)?"  # Upper bound is exclusive?
        "           (?P<range_upper_desc_version>{version_group})?"
        "           (?(range_upper_desc_prefix)|\+)?"  # + only if upper bound is not exclusive
        "       )(?P<range_lower_desc>"
        "           (?(range_upper_desc_version),|)"  # Comma is not optional because we don't want to recognize something like "<4>3"
        "           (?P<range_lower_desc_prefix><(?={version_group})|>=?)"  # >= or > only if followed by a version group
        "           (?P<range_lower_desc_version>{version_group})?"
        "       )"
        "    )$"
    ).format(version_group=version_group)

    regex = re.compile(version_range_regex, re_flags)

    def __init__(self, input_string, make_token, invalid_bound_error=True):
        self.make_token = make_token
        self._groups = {}
        self._input_string = input_string
        self.bounds = []
        self.invalid_bound_error = invalid_bound_error

        is_any = False

        for part in input_string.split("|"):
            if part == '':
                # OR'ing anthing with the 'any' version range ('') will also
                # give the any range. Note that we can't early out here, as we
                # need to validate that the rest of the string is syntactically
                # correct
                #
                is_any = True
                self.bounds = []
                continue

            match = re.search(self.regex, part)
            if not match:
                raise ParseException("Syntax error in version range '%s'" % part)

            if is_any:
                # we're already the 'any' range regardless, so avoid more work
                continue

            self._groups = match.groupdict()

            # Note: the following is ordered by approx likelihood of use

            if self._groups['range_asc']:
                self._act_lower_and_upper_bound_asc()

            elif self._groups['version']:
                self._act_version()

            elif self._groups['lower_bound']:
                self._act_lower_bound()

            elif self._groups['exact_version']:
                self._act_exact_version()

            elif self._groups['range_desc']:
                self._act_lower_and_upper_bound_desc()

            elif self._groups['inclusive_bound']:
                self._act_bound()

            elif self._groups['upper_bound']:
                self._act_upper_bound()

    def _is_lower_bound_exclusive(self, token):
        return (token == ">")

    def _is_upper_bound_exclusive(self, token):
        return (token == "<")

    def _create_version_from_token(self, token):
        return Version(token, make_token=self.make_token)

    def action(fn):
        def fn_(self):
            result = fn(self)
            if self.debug:
                label = fn.__name__.replace("_act_", "")
                print("%-21s: %s" % (label, self._input_string))
                for key, value in self._groups.items():
                    print("    %-17s= %s" % (key, value))
                print("    %-17s= %s" % ("bounds", self.bounds))
            return result
        return fn_

    @action
    def _act_version(self):
        version = self._create_version_from_token(self._groups['version'])
        lower_bound = _LowerBound(version, True)
        upper_bound = _UpperBound(version.next(), False) if version else None

        self.bounds.append(_Bound(lower_bound, upper_bound))

    @action
    def _act_exact_version(self):
        version = self._create_version_from_token(self._groups['exact_version_group'])
        lower_bound = _LowerBound(version, True)
        upper_bound = _UpperBound(version, True)

        self.bounds.append(_Bound(lower_bound, upper_bound))

    @action
    def _act_bound(self):
        lower_version = self._create_version_from_token(self._groups['inclusive_lower_version'])
        lower_bound = _LowerBound(lower_version, True)

        upper_version = self._create_version_from_token(self._groups['inclusive_upper_version'])
        upper_bound = _UpperBound(upper_version, True)

        self.bounds.append(_Bound(lower_bound, upper_bound, self.invalid_bound_error))

    @action
    def _act_lower_bound(self):
        version = self._create_version_from_token(self._groups['lower_version'])
        exclusive = self._is_lower_bound_exclusive(self._groups['lower_bound_prefix'])
        lower_bound = _LowerBound(version, not exclusive)

        self.bounds.append(_Bound(lower_bound, None))

    @action
    def _act_upper_bound(self):
        version = self._create_version_from_token(self._groups['upper_version'])
        exclusive = self._is_upper_bound_exclusive(self._groups['upper_bound_prefix'])
        upper_bound = _UpperBound(version, not exclusive)

        self.bounds.append(_Bound(None, upper_bound))

    @action
    def _act_lower_and_upper_bound_asc(self):
        lower_bound = None
        upper_bound = None

        if self._groups['range_lower_asc']:
            version = self._create_version_from_token(self._groups['range_lower_asc_version'])
            exclusive = self._is_lower_bound_exclusive(self._groups['range_lower_asc_prefix'])
            lower_bound = _LowerBound(version, not exclusive)

        if self._groups['range_upper_asc']:
            version = self._create_version_from_token(self._groups['range_upper_asc_version'])
            exclusive = self._is_upper_bound_exclusive(self._groups['range_upper_asc_prefix'])
            upper_bound = _UpperBound(version, not exclusive)

        self.bounds.append(_Bound(lower_bound, upper_bound, self.invalid_bound_error))

    @action
    def _act_lower_and_upper_bound_desc(self):
        lower_bound = None
        upper_bound = None

        if self._groups['range_lower_desc']:
            version = self._create_version_from_token(self._groups['range_lower_desc_version'])
            exclusive = self._is_lower_bound_exclusive(self._groups['range_lower_desc_prefix'])
            lower_bound = _LowerBound(version, not exclusive)

        if self._groups['range_upper_desc']:
            version = self._create_version_from_token(self._groups['range_upper_desc_version'])
            exclusive = self._is_upper_bound_exclusive(self._groups['range_upper_desc_prefix'])
            upper_bound = _UpperBound(version, not exclusive)

        self.bounds.append(_Bound(lower_bound, upper_bound, self.invalid_bound_error))


class VersionRange(_Comparable):
    """Version range.

    A version range is a set of one or more contiguous ranges of versions. For
    example, "3.0 or greater, but less than 4" is a contiguous range that contains
    versions such as "3.0", "3.1.0", "3.99" etc. Version ranges behave something
    like sets - they can be intersected, added and subtracted, but can also be
    inverted. You can test to see if a Version is contained within a VersionRange.

    A VersionRange "3" (for example) is the superset of any version "3[.X.X...]".
    The version "3" itself is also within this range, and is smaller than "3.0"
    - any version with common leading tokens, but with a larger token count, is
    the larger version of the two.

    VersionRange objects have a flexible syntax that let you describe any
    combination of contiguous ranges, including inclusive and exclusive upper
    and lower bounds. This is best explained by example (those listed on the
    same line are equivalent):

        "3": 'superset' syntax, contains "3", "3.0", "3.1.4" etc;
        "2+", ">=2": inclusive lower bound syntax, contains "2", "2.1", "5.0.0" etc;
        ">2": exclusive lower bound;
        "<5": exclusive upper bound;
        "<=5": inclusive upper bound;
        "==2": a range that contains only the exact single version "2".

        "1+<5", ">=1<5": inclusive lower, exclusive upper. The most common form of
            a 'bounded' version range (ie, one with a lower and upper bound);
        ">1<5": exclusive lower, exclusive upper;
        ">1<=5": exclusive lower, inclusive upper;
        "1+<=5", "1..5": inclusive lower, inclusive upper;

        "<=4,>2", "<4,>2", "<4,>=2": Reverse pip syntax (note comma)

    To help with readability, bounded ranges can also have their bounds separated
    with a comma, eg ">=2,<=6". The comma is purely cosmetic and is dropped in
    the string representation.

    To describe more than one contiguous range, seperate ranges with the or '|'
    symbol. For example, the version range "4|6+" contains versions such as "4",
    "4.0", "4.3.1", "6", "6.1", "10.0.0", but does not contain any version
    "5[.X.X...X]". If you provide multiple ranges that overlap, they will be
    automatically optimised - for example, the version range "3+<6|4+<8"
    becomes "3+<8".

    Note that the empty string version range represents the superset of all
    possible versions - this is called the "any" range. The empty version can
    also be used as an upper or lower bound, leading to some odd but perfectly
    valid version range syntax. For example, ">" is a valid range - read like
    ">''", it means "any version greater than the empty version".
    """
    def __init__(self, range_str='', make_token=AlphanumericVersionToken,
                 invalid_bound_error=True):
        """Create a VersionRange object.

        Args:
            range_str: Range string, such as "3", "3+<4.5", "2|6+". The range
                will be optimised, so the string representation of this instance
                may not match range_str. For example, "3+<6|4+<8" == "3+<8".
            make_token: Version token class to use.
            invalid_bound_error (bool): If True, raise an exception if an
                impossible range is given, such as '3+<2'.
        """
        self._str = None
        self.bounds = []  # note: kept in ascending order
        if range_str is None:
            return

        try:
            parser = _VersionRangeParser(range_str, make_token,
                                         invalid_bound_error=invalid_bound_error)
            bounds = parser.bounds
        except ParseException as e:
            raise VersionError("Syntax error in version range '%s': %s"
                               % (range_str, str(e)))
        except VersionError as e:
            raise VersionError("Invalid version range '%s': %s"
                               % (range_str, str(e)))

        if bounds:
            self.bounds = self._union(bounds)
        else:
            self.bounds.append(_Bound.any)

    def is_any(self):
        """Returns True if this is the "any" range, ie the empty string range
        that contains all versions."""
        return (len(self.bounds) == 1) and (self.bounds[0] == _Bound.any)

    def lower_bounded(self):
        """Returns True if the range has a lower bound (that is not the empty
        version)."""
        return self.bounds[0].lower_bounded()

    def upper_bounded(self):
        """Returns True if the range has an upper bound."""
        return self.bounds[-1].upper_bounded()

    def bounded(self):
        """Returns True if the range has a lower and upper bound."""
        return (self.lower_bounded() and self.upper_bounded())

    def issuperset(self, range):
        """Returns True if the VersionRange is contained within this range.
        """
        return self._issuperset(self.bounds, range.bounds)

    def issubset(self, range):
        """Returns True if we are contained within the version range.
        """
        return range.issuperset(self)

    def union(self, other):
        """OR together version ranges.

        Calculates the union of this range with one or more other ranges.

        Args:
            other: VersionRange object (or list of) to OR with.

        Returns:
            New VersionRange object representing the union.
        """
        if not hasattr(other, "__iter__"):
            other = [other]
        bounds = self.bounds[:]
        for range in other:
            bounds += range.bounds

        bounds = self._union(bounds)
        range = VersionRange(None)
        range.bounds = bounds
        return range

    def intersection(self, other):
        """AND together version ranges.

        Calculates the intersection of this range with one or more other ranges.

        Args:
            other: VersionRange object (or list of) to AND with.

        Returns:
            New VersionRange object representing the intersection, or None if
            no ranges intersect.
        """
        if not hasattr(other, "__iter__"):
            other = [other]

        bounds = self.bounds
        for range in other:
            bounds = self._intersection(bounds, range.bounds)
            if not bounds:
                return None

        range = VersionRange(None)
        range.bounds = bounds
        return range

    def inverse(self):
        """Calculate the inverse of the range.

        Returns:
            New VersionRange object representing the inverse of this range, or
            None if there is no inverse (ie, this range is the any range).
        """
        if self.is_any():
            return None
        else:
            bounds = self._inverse(self.bounds)
            range = VersionRange(None)
            range.bounds = bounds
            return range

    def intersects(self, other):
        """Determine if we intersect with another range.

        Args:
            other: VersionRange object.

        Returns:
            True if the ranges intersect, False otherwise.
        """
        return self._intersects(self.bounds, other.bounds)

    def split(self):
        """Split into separate contiguous ranges.

        Returns:
            A list of VersionRange objects. For example, the range "3|5+" will
            be split into ["3", "5+"].
        """
        ranges = []
        for bound in self.bounds:
            range = VersionRange(None)
            range.bounds = [bound]
            ranges.append(range)
        return ranges

    @classmethod
    def as_span(cls, lower_version=None, upper_version=None,
                lower_inclusive=True, upper_inclusive=True):
        """Create a range from lower_version..upper_version.

        Args:
            lower_version: Version object representing lower bound of the range.
            upper_version: Version object representing upper bound of the range.

        Returns:
            `VersionRange` object.
        """
        lower = (None if lower_version is None
                 else _LowerBound(lower_version, lower_inclusive))
        upper = (None if upper_version is None
                 else _UpperBound(upper_version, upper_inclusive))
        bound = _Bound(lower, upper)

        range = cls(None)
        range.bounds = [bound]
        return range

    @classmethod
    def from_version(cls, version, op=None):
        """Create a range from a version.

        Args:
            version: Version object. This is used as the upper/lower bound of
                the range.
            op: Operation as a string. One of 'gt'/'>', 'gte'/'>=', lt'/'<',
                'lte'/'<=', 'eq'/'=='. If None, a bounded range will be created
                that contains the version superset.

        Returns:
            `VersionRange` object.
        """
        lower = None
        upper = None

        if op is None:
            lower = _LowerBound(version, True)
            upper = _UpperBound(version.next(), False)
        elif op in ("eq", "=="):
            lower = _LowerBound(version, True)
            upper = _UpperBound(version, True)
        elif op in ("gt", ">"):
            lower = _LowerBound(version, False)
        elif op in ("gte", ">="):
            lower = _LowerBound(version, True)
        elif op in ("lt", "<"):
            upper = _UpperBound(version, False)
        elif op in ("lte", "<="):
            upper = _UpperBound(version, True)
        else:
            raise VersionError("Unknown bound operation '%s'" % op)

        bound = _Bound(lower, upper)
        range = cls(None)
        range.bounds = [bound]
        return range

    @classmethod
    def from_versions(cls, versions):
        """Create a range from a list of versions.

        This method creates a range that contains only the given versions and
        no other. Typically the range looks like (for eg) "==3|==4|==5.1".

        Args:
            versions: List of Version objects.

        Returns:
            `VersionRange` object.
        """
        range = cls(None)
        range.bounds = []
        for version in dedup(sorted(versions)):
            lower = _LowerBound(version, True)
            upper = _UpperBound(version, True)
            bound = _Bound(lower, upper)
            range.bounds.append(bound)
        return range

    def to_versions(self):
        """Returns exact version ranges as Version objects, or None if there
        are no exact version ranges present.
        """
        versions = []
        for bound in self.bounds:
            if bound.lower.inclusive and bound.upper.inclusive \
                    and (bound.lower.version == bound.upper.version):
                versions.append(bound.lower.version)

        return versions or None

    def contains_version(self, version):
        """Returns True if version is contained in this range."""
        if len(self.bounds) < 5:
            # not worth overhead of binary search
            for bound in self.bounds:
                i = bound.version_containment(version)
                if i == 0:
                    return True
                if i == -1:
                    return False
        else:
            _, contains = self._contains_version(version)
            return contains

        return False

    def iter_intersect_test(self, iterable, key=None, descending=False):
        """Performs containment tests on a sorted list of versions.

        This is more optimal than performing separate containment tests on a
        list of sorted versions.

        Args:
            iterable: An ordered sequence of versioned objects. If the list
                is not sorted by version, behaviour is undefined.
            key (callable): Function that returns a `Version` given an object
                from `iterable`. If None, the identity function is used.
            descending (bool): Set to True if `iterable` is in descending
                version order.

        Returns:
            An iterator that returns (bool, object) tuples, where 'object' is
            the original object in `iterable`, and the bool indicates whether
            that version is contained in this range.
        """
        return _ContainsVersionIterator(self, iterable, key, descending)

    def iter_intersecting(self, iterable, key=None, descending=False):
        """Like `iter_intersect_test`, but returns intersections only.

        Returns:
            An iterator that returns items from `iterable` that intersect.
        """
        return _ContainsVersionIterator(self, iterable, key, descending,
            mode=_ContainsVersionIterator.MODE_INTERSECTING)

    def iter_non_intersecting(self, iterable, key=None, descending=False):
        """Like `iter_intersect_test`, but returns non-intersections only.

        Returns:
            An iterator that returns items from `iterable` that don't intersect.
        """
        return _ContainsVersionIterator(self, iterable, key, descending,
            mode=_ContainsVersionIterator.MODE_NON_INTERSECTING)

    def span(self):
        """Return a contiguous range that is a superset of this range.

        Returns:
            A VersionRange object representing the span of this range. For
            example, the span of "2+<4|6+<8" would be "2+<8".
        """
        other = VersionRange(None)
        bound = _Bound(self.bounds[0].lower, self.bounds[-1].upper)
        other.bounds = [bound]
        return other

    # TODO have this return a new VersionRange instead - this currently breaks
    # VersionRange immutability, and could invalidate __str__.
    def visit_versions(self, func):
        """Visit each version in the range, and apply a function to each.

        This is for advanced usage only.

        If `func` returns a `Version`, this call will change the versions in
        place.

        It is possible to change versions in a way that is nonsensical - for
        example setting an upper bound to a smaller version than the lower bound.
        Use at your own risk.

        Args:
            func (callable): Takes a `Version` instance arg, and is applied to
                every version in the range. If `func` returns a `Version`, it
                will replace the existing version, updating this `VersionRange`
                instance in place.
        """
        for bound in self.bounds:
            if bound.lower is not _LowerBound.min:
                result = func(bound.lower.version)
                if isinstance(result, Version):
                    bound.lower.version = result

            if bound.upper is not _UpperBound.inf:
                result = func(bound.upper.version)
                if isinstance(result, Version):
                    bound.upper.version = result

    def __contains__(self, version_or_range):
        if isinstance(version_or_range, Version):
            return self.contains_version(version_or_range)
        else:
            return self.issuperset(version_or_range)

    def __len__(self):
        return len(self.bounds)

    def __invert__(self):
        return self.inverse()

    def __and__(self, other):
        return self.intersection(other)

    def __or__(self, other):
        return self.union(other)

    def __add__(self, other):
        return self.union(other)

    def __sub__(self, other):
        inv = other.inverse()
        return None if inv is None else self.intersection(inv)

    def __str__(self):
        if self._str is None:
            self._str = '|'.join(map(str, self.bounds))
        return self._str

    def __eq__(self, other):
        return isinstance(other, VersionRange) and self.bounds == other.bounds

    def __lt__(self, other):
        return (self.bounds < other.bounds)

    def __hash__(self):
        return hash(tuple(self.bounds))

    def _contains_version(self, version):
        vbound = _Bound(_LowerBound(version, True))
        i = bisect_left(self.bounds, vbound)
        if i and self.bounds[i - 1].contains_version(version):
            return i - 1, True
        if (i < len(self.bounds)) and self.bounds[i].contains_version(version):
            return i, True
        return i, False

    @classmethod
    def _union(cls, bounds):
        if len(bounds) < 2:
            return bounds

        bounds_ = list(sorted(bounds))
        new_bounds = []
        prev_bound = None
        upper = None
        start = 0

        for i, bound in enumerate(bounds_):
            if i and ((bound.lower.version > upper.version)
                      or ((bound.lower.version == upper.version)
                          and (not bound.lower.inclusive)
                          and (not prev_bound.upper.inclusive))):
                new_bound = _Bound(bounds_[start].lower, upper)
                new_bounds.append(new_bound)
                start = i

            prev_bound = bound
            upper = bound.upper if upper is None else max(upper, bound.upper)

        new_bound = _Bound(bounds_[start].lower, upper)
        new_bounds.append(new_bound)
        return new_bounds

    @classmethod
    def _intersection(cls, bounds1, bounds2):
        new_bounds = []
        for bound1 in bounds1:
            for bound2 in bounds2:
                b = bound1.intersection(bound2)
                if b:
                    new_bounds.append(b)
        return new_bounds

    @classmethod
    def _inverse(cls, bounds):
        lbounds = [None]
        ubounds = []

        for bound in bounds:
            if not bound.lower.version and bound.lower.inclusive:
                ubounds.append(None)
            else:
                b = _UpperBound(bound.lower.version, not bound.lower.inclusive)
                ubounds.append(b)

            if bound.upper.version == Version.inf:
                lbounds.append(None)
            else:
                b = _LowerBound(bound.upper.version, not bound.upper.inclusive)
                lbounds.append(b)

        ubounds.append(None)
        new_bounds = []

        for lower, upper in zip(lbounds, ubounds):
            if not (lower is None and upper is None):
                new_bounds.append(_Bound(lower, upper))

        return new_bounds

    @classmethod
    def _issuperset(cls, bounds1, bounds2):
        lo = 0
        for bound2 in bounds2:
            i = bisect_left(bounds1, bound2, lo=lo)
            if i and bounds1[i - 1].contains_bound(bound2):
                lo = i - 1
                continue
            if (i < len(bounds1)) and bounds1[i].contains_bound(bound2):
                lo = i
                continue
            return False

        return True

    @classmethod
    def _intersects(cls, bounds1, bounds2):
        # sort so bounds1 is the shorter list
        bounds1, bounds2 = sorted((bounds1, bounds2), key=lambda x: len(x))

        if len(bounds2) < 5:
            # not worth overhead of binary search
            for bound1 in bounds1:
                for bound2 in bounds2:
                    if bound1.intersects(bound2):
                        return True
            return False

        lo = 0
        for bound1 in bounds1:
            i = bisect_left(bounds2, bound1, lo=lo)
            if i and bounds2[i - 1].intersects(bound1):
                return True
            if (i < len(bounds2)) and bounds2[i].intersects(bound1):
                return True
            lo = max(i - 1, 0)

        return False


class _ContainsVersionIterator(object):
    MODE_INTERSECTING = 0
    MODE_NON_INTERSECTING = 2
    MODE_ALL = 3

    def __init__(self, range_, iterable, key=None, descending=False, mode=MODE_ALL):
        self.mode = mode
        self.range_ = range_
        self.index = None
        self.nbounds = len(self.range_.bounds)
        self._constant = True if range_.is_any() else None
        self.fn = self._descending if descending else self._ascending
        self.it = iter(iterable)
        if key is None:
            key = lambda x: x
        self.keyfunc = key

        if mode == self.MODE_ALL:
            self.next_fn = self._next
        elif mode == self.MODE_INTERSECTING:
            self.next_fn = self._next_intersecting
        else:
            self.next_fn = self._next_non_intersecting

    def __iter__(self):
        return self

    def __next__(self):
        return self.next_fn()

    def next(self):
        return self.next_fn()

    def _next(self):
        value = next(self.it)
        if self._constant is not None:
            return self._constant, value

        version = self.keyfunc(value)
        intersects = self.fn(version)
        return intersects, value

    def _next_intersecting(self):
        while True:
            value = next(self.it)

            if self._constant:
                return value
            elif self._constant is not None:
                raise StopIteration

            version = self.keyfunc(value)
            intersects = self.fn(version)
            if intersects:
                return value

    def _next_non_intersecting(self):
        while True:
            value = next(self.it)

            if self._constant:
                raise StopIteration
            elif self._constant is not None:
                return value

            version = self.keyfunc(value)
            intersects = self.fn(version)
            if not intersects:
                return value

    @property
    def _bound(self):
        if self.index < self.nbounds:
            return self.range_.bounds[self.index]
        else:
            return None

    def _ascending(self, version):
        if self.index is None:
            self.index, contains = self.range_._contains_version(version)
            bound = self._bound
            if contains:
                if not bound.upper_bounded():
                    self._constant = True
                return True
            elif bound is None:  # past end of last bound
                self._constant = False
                return False
            else:
                return False  # there are more bound(s) ahead
        else:
            bound = self._bound
            j = bound.version_containment(version)
            if j == 0:
                return True
            elif j == -1:
                return False
            else:
                while True:
                    self.index += 1
                    bound = self._bound
                    if bound is None:  # past end of last bound
                        self._constant = False
                        return False
                    else:
                        j = bound.version_containment(version)
                        if j == 0:
                            if not bound.upper_bounded():
                                self._constant = True
                            return True
                        elif j == -1:
                            return False

    def _descending(self, version):
        if self.index is None:
            self.index, contains = self.range_._contains_version(version)
            bound = self._bound
            if contains:
                if not bound.lower_bounded():
                    self._constant = True
                return True
            elif bound is None:  # past end of last bound
                self.index = self.nbounds - 1
                return False
            elif self.index == 0:  # before start of first bound
                self._constant = False
                return False
            else:
                self.index -= 1
                return False
        else:
            bound = self._bound
            j = bound.version_containment(version)
            if j == 0:
                return True
            elif j == 1:
                return False
            else:
                while self.index:
                    self.index -= 1
                    bound = self._bound
                    j = bound.version_containment(version)
                    if j == 0:
                        if not bound.lower_bounded():
                            self._constant = True
                        return True
                    elif j == 1:
                        return False

                self._constant = False  # before start of first bound
                return False
