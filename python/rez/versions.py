"""
This module contains classes which operate on version strings. Example version strings include:
'', '1', '1.2.3', '3.5+', '3.5+<4', '10.5|11.2', '10.5|11+', '1.2.a'.
Character components are allowed, and are ordered alphabetically, ie '1.b' > '1.a', however if
a component is a valid number then it is treated numerically, not alphabetically. Only single
characters 'a'-'z' are allowed.

Operations such as unions and intersections are possible. For example, the version '10.5' is
considered the superset of any version of the form '10.5.x', so union(10.5, 10.5.4) would be
'10.5'.

A single version string can describe sets of disparate version ranges - for example, '10.5|5.4|7'.
A version is said to be 'inexact' if it definitely describes a range of versions, for example
'4.5+', '1.0|2.0', '', '4.5+<5.0'. A version string is never said to be 'exact', because whether
this is true depends on context - for example the version '10.5' may represent an exact version
in one case, but may represent the superset of all versions '10.5.x' in another.
"""
import re

# can't be zero padded
VERSION_COMPONENT_REGSTR = '(?:[0-9a-z]|[1-9][0-9]+)'
EXACT_VERSION_REGSTR = '%(comp)s(?:[.]%(comp)s)*' % dict(comp=VERSION_COMPONENT_REGSTR)
LABEL_VERSION_REGSTR = '[a-zA-Z][a-zA-Z0-9_]+'
EXACT_VERSION_REG = re.compile(EXACT_VERSION_REGSTR + "$")
LABEL_VERSION_REG = re.compile(LABEL_VERSION_REGSTR + "$")

def is_character(tok):
    """
    tests whether a string is a single lowercase character
    """
    return len(tok) == 1 and tok.islower()

def to_component(tok, version_str):
    if len(tok) == 0:
        raise VersionError("Version string resulted in empty token: '%s'" % version_str)

    if (tok[0] == '0') and (tok != '0'):  # zero-padding is not allowed, eg '03'
        raise VersionError("Version components cannot have padding: '%s' (%s')" % (tok, version_str))

    try:
        i = int(tok)
        if i < 0:
            raise VersionError("Version components cannot be negative: '%s' (%s')" % (tok, version_str))
        return i
    except ValueError:
        if is_character(tok):
            return tok
        else:
            raise VersionError("'%s'" % version_str)

def parse_exact_version(version):
    """
    Parse an exact version into a tuple of component integers
    """
    # FIXME: do we still need to support dash separators?
    tokens = version.replace('-', '.').split('.')
    return tuple(to_component(tok, version) for tok in tokens)

def strip_trailing_zeros(bound):
    bound = list(bound)
    while (len(bound) > 1) and (bound[-1] == 0):
        bound.pop()
    return tuple(bound)

def incr_component(comp):
    """
    increment a number or single character by 1
    """
    if isinstance(comp, int):
        return comp + 1
    elif isinstance(comp, basestring) and is_character(comp):
        return chr(ord(comp) + 1)
    else:
        raise VersionError("Component must be an int or a single character: %r" % comp)

def incr_bound(bound):
    """
    increment the last component of a bound by 1
    """
    return bound[:-1] + tuple([incr_component(bound[-1])])

class VersionError(Exception):
    """
    Exception
    """
    def __init__(self, value=None):
        self.value = value

    def __str__(self):
        return "Invalid version: %s" % self.value

class Version(object):
    """
    Interprets a version string representing a single contiguous range of versions.

    For a union of disparate version ranges (separated with '|'s)
    use a VersionRange.
    """

    INF = (999999,)
    NEG_INF = (-999999,)
    ZERO = (0,)

    def __init__(self, version=None):
        if isinstance(version, (list, tuple)):
            self._ge = tuple(version[0])
            self._lt = tuple(version[1])
            assert len(self._ge)
            assert len(self._lt)

        elif version:
            try:
                version = str(version)
            except UnicodeEncodeError:
                raise VersionError("Non-ASCII characters in version string")

            parts = version.split("+<")
            if len(parts) == 1:
                plus = version.endswith('+')
                self._ge = parse_exact_version(version.rstrip('+'))

                if plus:
                    # no upper bound
                    self._lt = Version.INF
                else:
                    # upper bound is one higher than lower bound
                    # Note: we can be sure that self.ge is bounded here (not infinity),
                    # because empty version string routes elsewhere.
                    self._lt = incr_bound(self._ge)

            else:
                # lower bound is the lower bound of first version:
                self._ge = parse_exact_version(parts[0])
                # upper bound is the non-inclusive lower bound of second version:
                # remove trailing zeros on lt bound (think: 'A < 1.0.0' == 'A < 1')
                # this also makes this version invalid: '1+<1.0.0'
                self._lt = strip_trailing_zeros(parse_exact_version(parts[1]))

                if self.lt <= self.ge:
                    raise VersionError("Upper bound '%s' is less than or equal "
                                       "to lower bound '%s': '%s'" % (parts[0],
                                                                      parts[1],
                                                                      version))
        else:
            # empty string or none results in an unbounded version
            self._ge = Version.NEG_INF
            self._lt = Version.INF

    @property
    def ge(self):
        return self._ge

    @property
    def lt(self):
        return self._lt

    def copy(self):
        # Version is immutable. no need to copy
        return self

    def get_ge_plus_one(self):
        if self.ge == Version.NEG_INF:
            return Version.INF
        return incr_bound(self.ge)

    def is_inexact(self):
        """
        Return true if version is inexact. e.g. '10.5+' or '10.5+<10.7'

        .. note:: not is_inexact() does not imply exact - for
        eg, the version '10.5' *may* refer to any version of '10.5.x', but we
        cannot know this without inspecting the package. Thus, the Version class
        on its own can only know when it is inexact, and never when it is exact.
        """
        return self.lt != self.get_ge_plus_one()

    def is_any(self):
        """
        Return true if version is 'any', ie was created from an empty string
        """
        return self.ge == Version.NEG_INF and self.lt == Version.INF

    def contains_version(self, version):
        """
        Returns True if the exact version (eg 1.0.0) is contained within this range.

        accepts a Version instance or a version ge.
        """
        return (version.ge >= self.ge) and (version.lt <= self.lt)

    def get_union(self, ver):
        """
        Return new version(s) representing the union of this and another version.
        The result may be more than one version, so a version list is returned.
        """
        if self.ge >= ver.lt or self.lt <= ver.ge:
            return sorted([self, ver])
        # FIXME: if the lt of the new Version is not INF, should we set ge to ZERO?
        v = Version([min(self.ge, ver.ge),
                     max(self.lt, ver.lt)])
        return [v]

    def get_span(self, version):
        """"
        Return a single version spanning the low bound of the current version,
        and the high bound of the passed version.
        """
        if (self.ge == Version.NEG_INF) and (version.lt != Version.INF):
            return Version([Version.ZERO, version.lt])
        else:
            return Version([self.ge, version.lt])

    def get_intersection(self, ver):
        """
        Return a new version representing the intersection between this and
        another version, or None if the versions do not overlap
        """
        if ver.ge >= self.lt or ver.lt <= self.ge:
            return None

        if ver.ge > self.ge:
            ge = ver.ge
        else:
            ge = self.ge
        if ver.lt < self.lt:
            lt = ver.lt
        else:
            lt = self.lt
        return Version([ge, lt])

    def __str__(self):
        def get_str(parts):
            return ".".join([str(part) for part in parts])

        if self.lt == Version.INF:
            if self.ge == Version.NEG_INF:
                return ""
            else:
                return get_str(self.ge) + "+"
        elif self.is_inexact():
            return get_str(self.ge) + "+<" + get_str(self.lt)
        else:
            return get_str(self.ge)

    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__, self)

    def __lt__(self, ver):
        """
        less-than test. Version A is < B if A's ge bound is < B's. If the ge
        bounds are the same, the lt bounds are then tested, and A is < B if its
        lt bound is < B's.
        """
        if self.ge == ver.ge:
            return self.lt < ver.lt
        else:
            return self.ge < ver.ge

    def __eq__(self, ver):
        return self.ge == ver.ge and self.lt == ver.lt

    def __le__(self, ver):
        return self.__lt__(ver) or self.__eq__(ver)

    def __contains__(self, version):
        if isinstance(version, basestring):
            version = Version(version)
        return self.contains_version(version)

    def __hash__(self):
        return hash(str(self))

class VersionRange(object):
    """
    A collection of zero or more inexact versions, which do not overlap. If a
    VersionRange is initialised with disparate version ranges which do overlap
    (eg '10.5+|10.5.2'), these will be resolved at initialization.
    """

    def __init__(self, version):
        if isinstance(version, (list, tuple)):
            versions = [Version(v) for v in version]
            self.versions = tuple(get_versions_union(versions))
        elif isinstance(version, Version):
            self.versions = (version,)
        elif isinstance(version, VersionRange):
            self.versions = version.versions
        else:
            try:
                version = str(version)
            except:
                raise VersionError("Version range must be initialized with string, "
                                   "list, tuple, or Version instance. got %s" % type(version).__name__)
            else:
                versions = [Version(v) for v in version.split("|")]
                self.versions = tuple(get_versions_union(versions))

    def copy(self):
        # is immutable, no need to copy
        return self

    def contains_version(self, version):
        """
        Returns True if the exact version (eg 1.0.0) is contained within this range.
        """
        for ver in self.versions:
            if ver.contains_version(version):
                return True
        return False

    def matches_version(self, ver, allow_inexact=False):
        """
        Returns True if the range matches the Version.

        If `allow_inexact` is True, considers inexact matches as well.
        """
        # if the range is not inexact, then there is only one version
        if not self.is_inexact() and ver == self.versions[0]:
            return True
        # Note that VersionRange('').contains_version('10') == True
        if allow_inexact and self.contains_version(ver):
            return True
        return False

    def get_union(self, vers):
        """
        get union
        """
        union = get_versions_union(self.versions + vers.versions)
        return VersionRange(union)

    def get_span(self):
        """"
        Return a single version spanning the low and high versions of the range,
        Or None if range contains no versions.
        """
        if len(self.versions) > 0:
            return self.versions[0].get_span(self.versions[-1])

    def get_intersection(self, vers):
        """
        get intersection
        """
        vers_int = []
        if isinstance(vers, Version):
            vers = [vers]
        else:
            vers = vers.versions
        for ver in self.versions:
            for ver2 in vers:
                vint = ver.get_intersection(ver2)
                if vint:
                    vers_int.append(vint)

        if (len(vers_int) == 0):
            return VersionRange([])
        else:
            return VersionRange(vers_int)

    def get_inverse(self):
        """
        get the inverse of this version range
        """
        # inverse of any is none
        if self.is_any():
            return VersionRange([])

        # the inverse of none is any
        if self.is_none():
            return VersionRange('')

        # inverse is the ranges between existing ranges
        vers_inv = []

        ver_front = Version([Version.NEG_INF,
                             incr_bound(Version.NEG_INF)])

        ver_back = Version([Version.INF,
                            incr_bound(Version.INF)])

        vers = [ver_front] + list(self.versions) + [ver_back]
        for i in range(0, len(vers) - 1):
            v0 = vers[i]
            v1 = vers[i + 1]
            if v0.lt < v1.ge:
                v = Version([v0.lt, v1.ge])
                vers_inv.append(v)

        if len(vers_inv) > 0:
            # clamp ge limits back to zero
            if vers_inv[0].lt <= Version.ZERO:
                vers_inv = vers_inv[1:]

            if len(vers_inv) > 0 and vers_inv[0].ge < Version.ZERO:
                vers_inv[0] = Version([Version.ZERO,
                                       strip_trailing_zeros(vers_inv[0].lt)])
                # we may get something like this when clamping: 0+<0.0, which
                # is not valid, so detect it and remove it
                if vers_inv[0].lt == vers_inv[0].ge:
                    vers_inv.pop(0)

        return VersionRange(vers_inv)

    def is_greater_no_overlap(self, ver):
        """
        return True if the given version range is greater than this one,
        and there is no overlap
        """
        if len(self.versions) == 0 and len(ver.versions) == 0:
            return False
        elif len(self.versions) == 0 or len(ver.versions) == 0:
            return True
        return ver.versions[0].ge >= self.versions[-1].lt

    def is_inexact(self):
        """
        return True if the version range is inexact
        """
        if len(self.versions) == 0:
            return False
        return (len(self.versions) > 1) or self.versions[0].is_inexact()

    def is_any(self):
        """
        Return true if version is 'any', ie was created from an empty string
        """
        return (len(self.versions) == 1) and self.versions[0].is_any()

    def is_none(self):
        """
        Return true if this range describes no versions
        """
        return len(self.versions) == 0

    def get_dim(self):
        """
        Returns the number of distinct versions in the range
        """
        return len(self.versions)

    def __str__(self):
        return "|".join(str(v) for v in self.versions)

    def __repr__(self):
        # differential between any and none
        if self.is_none():
            return "%s([])" % (self.__class__.__name__,)
        return "%s('%s')" % (self.__class__.__name__, self)

    def __eq__(self, ver):
        """
        equality test
        """
        if ver is None:
            return False
        return self.versions == ver.versions

    def __ne__(self, ver):
        """
        inequality test
        """
        return not self == ver

    def __contains__(self, version):
        if isinstance(version, basestring):
            version = Version(version)
        return self.contains_version(version)

    def __hash__(self):
        return hash(str(self))

    def __nonzero__(self):
        return not self.is_none()

def get_versions_union(versions):
    """Returns a sorted list of Version instances"""
    nvers = len(versions)
    if nvers == 0:
        return []
    elif nvers == 1:
        return list(versions)
    elif nvers == 2:
        return versions[0].get_union(versions[1])
    else:
        new_versions = []
        idx = 1
        versions_tmp = sorted(versions)
        for ver1 in versions_tmp:
            overlap = False
            for i, ver2 in enumerate(versions_tmp[idx:]):
                ver_union = ver1.get_union(ver2)
                if len(ver_union) == 1:
                    # replace
                    versions_tmp[idx + i] = ver_union[0]
                    overlap = True
                    break
            if not overlap:
                new_versions.append(ver1)
            idx += 1
        return sorted(new_versions)


# This class is currently only used the ResolvedPackage and the rex command language
# but it would be great to merge its functionality into the Version class
class ExactVersion(Version):
    """
    Provide access to version parts and perform common reformatting
    """
    LABELS = {'major': 1,
              'minor': 2,
              'patch': 3}

# 	def __new__(self, s):
# 		if EXACT_VERSION_REG.match(s):
# 			self.numeric = True
# 		elif LABEL_VERSION_REG.match(s):
# 			self.numeric = False
# 		else:
# 			raise ValueError("Not a valid exact version: %r" % s)
# 		return str.__new__(self, s)

    def __init__(self, version):
        try:
            self.version = str(version)
        except UnicodeEncodeError:
            raise VersionError("Non-ASCII characters in version string")
        if LABEL_VERSION_REG.match(self.version):
            self._ge = Version.NEG_INF
            self._lt = Version.NEG_INF
        else:
            self._ge = parse_exact_version(self.version)
            # upper bound is one higher than lower bound
            # Note: we can be sure that self.ge is bounded here (not infinity),
            # because empty version string routes elsewhere.
            self._lt = incr_bound(self._ge)

    def contains_version(self, version):
        """
        Returns True if the exact version (eg 1.0.0) is equal.
        """
        return self == version

    @property
    def major(self):
        return self.part(self.LABELS['major'])

    @property
    def minor(self):
        return self.part(self.LABELS['minor'])

    @property
    def patch(self):
        return self.part(self.LABELS['patch'])

    def part(self, num):
        num = int(num)
        if num == 0:
            print "warning: version.part() got index 0: converting to 1"
            num = 1
        try:
            return self.version.split('.')[num - 1]
        except IndexError:
            return ''

    def thru(self, num):
        try:
            num = int(num)
        except ValueError:
            if isinstance(num, basestring):
                try:
                    num = self.LABELS[num]
                except KeyError:
                    # allow to specify '3' as 'x.x.x'
                    num = len(num.split('.'))
            else:
                raise
        if num == 0:
            print "warning: version.thru() got index 0: converting to 1"
            num = 1
        try:
            return '.'.join(self.version.split('.')[:num])
        except IndexError:
            return ''

    def __lt__(self, ver):
        if self.ge == Version.NEG_INF:
            return self.version < str(ver)
        else:
            return super(ExactVersion, self).__lt__(ver)

    def __eq__(self, other):
        return self.version == str(other)

    def __le__(self, ver):
        if self.ge == Version.NEG_INF:
            return self.version <= str(ver)
        else:
            return super(ExactVersion, self).__le__(ver)

    def __str__(self):
        return self.version

    def matches_version(self, other, allow_inexact=False):
        return self == other

    def is_inexact(self):
        return False

    def get_intersection(self, ver):
        """
        Return a new version representing the intersection between this and
        another version, or None if the versions do not overlap
        """
        if self == ver:
            return self
        else:
            return None

class ExactVersionSet(VersionRange):
    def __init__(self, version):
        if isinstance(version, (list, tuple)):
            self.versions = sorted([ExactVersion(v) for v in version])
        elif isinstance(version, ExactVersion):
            self.versions = (version,)
        elif isinstance(version, ExactVersionSet):
            self.versions = version.versions
        elif isinstance(version, basestring):
            # just make sure it's a string, because sometimes we pass in a Version instance
            self.versions = sorted([ExactVersion(v) for v in version.split("|")])
        else:
            raise VersionError("Version range must be initialized with string, "
                               "list, tuple, or ExactVersion instance. got %s" % type(version).__name__)

    def contains_version(self, version):
        return version in self.versions

    def matches_version(self, ver, allow_inexact=False):
        """
        Returns True if the range matches the Version.

        If `allow_inexact` is True, considers inexact matches as well.
        """
        # if the range is not inexact, then there is only one version
        if not self.is_inexact() and ver == self.versions[0]:
            return True
        # Note that VersionRange('').contains_version('10') == True
        if allow_inexact and self.contains_version(ver):
            return True
        return False

    def get_union(self, vers):
        """
        get union
        """
        versions = set(self.versions)
        if isinstance(vers, ExactVersion):
            vers = [vers]
        else:
            vers = vers.versions
        return ExactVersionSet(sorted(versions.union(vers)))

    def get_span(self):
        """"
        Return a single version spanning the low and high versions of the range,
        Or None if range contains no versions.
        """
        raise NotImplementedError

    def get_intersection(self, vers):
        """
        get intersection, return None if there are no intersections
        """
        versions = set(self.versions)
        if isinstance(vers, ExactVersion):
            vers = [vers]
        else:
            vers = vers.versions
        return ExactVersionSet(list(versions.intersection(vers)))

    def get_inverse(self):
        """
        get the inverse of this version range
        """
        raise NotImplementedError

# 	def is_greater_no_overlap(self, ver):
# 		"""
# 		return True if the given version range is greater than this one,
# 		and there is no overlap
# 		"""
# 		if len(self.versions) == 0 and len(ver.versions) == 0:
# 			return False
# 		elif len(self.versions) == 0 or len(ver.versions) == 0:
# 			return True
# 		return ver.versions[0].ge >= self.versions[-1].lt


#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
