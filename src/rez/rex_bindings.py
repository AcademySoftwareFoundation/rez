"""
Provides wrappers for various types for binding to Rex. We do not want to bind
object instances directly in Rex, because this would create an indirect
dependency between rex code in package.py files, and versions of Rez.

The classes in this file are intended to have simple interfaces that hide
unnecessary data from Rex, and provide APIs that will not change.
"""
from rez.vendor.six import six
from rez.vendor.version.version import VersionRange
from rez.vendor.version.requirement import Requirement


basestring = six.string_types[0]


class Binding(object):
    """Abstract base class."""
    def __init__(self, data=None):
        self._data = data or {}

    def _attr_error(self, attr):
        raise AttributeError("%s has no attribute '%s'"
                             % (self.__class__.__name__, attr))

    def __getattr__(self, attr):
        try:
            return self._data[attr]
        except KeyError:
            self._attr_error(attr)


class VersionBinding(Binding):
    """Binds a version.Version object.

        >>> v = VersionBinding(Version("1.2.3alpha"))
        >>> v.major
        1
        >>> v.patch
        '3alpha'
        >>> len(v)
        3
        >>> v[1]
        2
        >>> v[:3]
        (1, 2, '3alpha')
        >>> str(v)
        '1.2.3alpha'
        >>> print(v[5])
        None
        >>> v.as_tuple():
        (1, 2, '3alpha')
    """
    def __init__(self, version):
        super(VersionBinding, self).__init__()
        self.__version = version

    @property
    def major(self):
        return self[0]

    @property
    def minor(self):
        return self[1]

    @property
    def patch(self):
        return self[2]

    def as_tuple(self):
        return self[:len(self)]

    def _attr_error(self, attr):
        raise AttributeError("version %s has no attribute '%s'"
                             % (str(self), attr))

    def __getitem__(self, i):
        try:
            return self.__getitem(i)
        except IndexError:
            return None

    def __getitem(self, i):
        def _convert(t):
            s = str(t)
            if s.isdigit() and (s[0] != '0' or s == '0'):
                return int(s)
            else:
                return s

        tokens = self.__version[i]
        if hasattr(tokens, "__iter__"):
            return tuple(map(_convert, tokens))
        else:
            return _convert(tokens)

    def __len__(self):
        return len(self.__version)

    def __str__(self):
        return str(self.__version)

    def __iter__(self):
        # without this, the binding will iterate infinitely, returning more
        # None objects...
        return iter(self.__version)


class VariantBinding(Binding):
    """Binds a packages.Variant object."""
    def __init__(self, variant, cached_root=None):
        doc = dict(version=VersionBinding(variant.version))
        super(VariantBinding, self).__init__(doc)
        self.__variant = variant
        self.__cached_root = cached_root

    @property
    def root(self):
        """
        This is here to support package caching. This ensures that references
        such as 'resolve.mypkg.root' resolve to the cached payload location,
        if the package is cached.
        """
        return self.__cached_root or self.__variant.root

    def __getattr__(self, attr):
        try:
            return super(VariantBinding, self).__getattr__(attr)
        except:
            value = getattr(self.__variant, attr, KeyError)
            if value is KeyError:
                raise

            return value

    def _is_in_package_cache(self):
        return (self.__cached_root is not None)

    def _attr_error(self, attr):
        raise AttributeError("package %s has no attribute '%s'"
                             % (str(self), attr))

    def __str__(self):
        return self.__variant.qualified_package_name


class RO_MappingBinding(Binding):
    """A read-only, dict-like object.
    """
    def __init__(self, data):
        super(RO_MappingBinding, self).__init__(data)

    def get(self, name, default=None):
        return self._data.get(name, default)

    def __getitem__(self, name):
        if name in self._data:
            return self._data[name]
        else:
            self._attr_error(name)

    def __contains__(self, name):
        return (name in self._data)

    def __str__(self):
        return str(self._data.values())


class VariantsBinding(RO_MappingBinding):
    """Binds a list of packages.VariantBinding objects, under the package name
    of each variant."""
    def __init__(self, variant_bindings):
        super(VariantsBinding, self).__init__(variant_bindings)

    def _attr_error(self, attr):
        raise AttributeError("package does not exist: '%s'" % attr)


class RequirementsBinding(RO_MappingBinding):
    """Binds a list of version.Requirement objects."""
    def __init__(self, requirements):
        doc = dict((x.name, str(x)) for x in requirements)
        super(RequirementsBinding, self).__init__(doc)

    def _attr_error(self, attr):
        raise AttributeError("request does not exist: '%s'" % attr)

    def get_range(self, name, default=None):
        """Returns requirement version range object"""
        req_str = self._data.get(name)
        if req_str:
            return Requirement(req_str).range
        elif default is not None:
            return VersionRange(default)
        else:
            return None


class EphemeralsBinding(RO_MappingBinding):
    """Binds a list of resolved ephemeral packages.

    Note that the leading '.' is implied when referring to ephemerals. Eg:

        # in package.py
        def commands():
            if "foo.cli" in ephemerals:  # will match '.foo.cli-*' request
    """
    def __init__(self, ephemerals):
        doc = dict(
            (x.name[1:], str(x))  # note: stripped leading '.'
            for x in ephemerals
        )
        super(EphemeralsBinding, self).__init__(doc)

    def _attr_error(self, attr):
        raise AttributeError("ephemeral does not exist: '%s'" % attr)

    def get_range(self, name, default=None):
        """Returns ephemeral version range object"""
        req_str = self._data.get(name)
        if req_str:
            return Requirement(req_str).range
        elif default is not None:
            return VersionRange(default)
        else:
            return None


def intersects(obj, range_):
    """Test if an object intersects with the given version range.

    Examples:

        # in package.py
        def commands():
            # test a request
            if intersects(request.maya, '2019+'):
                info('requested maya allows >=2019.*')

            # tests if a resolved version intersects with given range
            if intersects(resolve.maya, '2019+')
                ...

            # same as above
            if intersects(resolve.maya.version, '2019+')
                ...

        # disable my cli tools if .foo.cli-0 was specified
        def commands():
            if intersects(ephemerals.get('foo.cli', '1'), '1'):
                env.PATH.append('{root}/bin')

    Args:
        obj (VariantBinding or str): Object to test, either a
            variant, or requirement string (eg 'foo-1.2.3+').
        range_ (str): Version range, eg '1.2+<2'

    Returns:
        bool: True if the object intersects the given range.
    """
    range1 = VersionRange(range_)

    # eg 'if intersects(request.maya, ...)'
    if isinstance(obj, basestring):
        req = Requirement(obj)
        if req.conflict:
            return False
        range2 = req.range

    # eg 'if intersects(ephemerals.get_range('foo.cli', '1'), ...)'
    elif isinstance(obj, VersionRange):
        range2 = obj

    # eg 'if intersects(resolve.maya, ...)'
    elif isinstance(obj, VariantBinding):
        range2 = VersionRange(str(obj.version))

    # eg 'if intersects(resolve.maya.version, ...)'
    elif isinstance(obj, VersionBinding):
        range2 = VersionRange(str(obj))

    else:
        raise RuntimeError(
            "Invalid type %s passed as first arg to 'intersects'" % type(obj)
        )

    return range1.intersects(range2)


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
