"""
Provides wrappers for various types for binding to Rex. We do not want to bind
object instances directly in Rex, because this would create an indirect
dependency between rex code in package.* files, and versions of Rez.

The classes in this file are intended to have simple interfaces that hide
unnecessary data from Rex, and provide APIs that will not change.
"""


class Binding(object):
    """Abstract base class."""
    def __init__(self, data=None):
        self.__data = data or {}

    def _attr_error(self, attr):
        raise AttributeError("%s has no attribute '%s'"
                             % (self.__class__.__name__, attr))

    def __getattr__(self, attr):
        try:
            return self.__data[attr]
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
    def __init__(self, variant):
        doc = dict(version=VersionBinding(variant.version))
        super(VariantBinding, self).__init__(doc)
        self.__variant = variant

    # hacky, but we'll be deprecating all these bindings..
    def __getattr__(self, attr):
        try:
            return super(VariantBinding, self).__getattr__(attr)
        except:
            missing = object()
            value = getattr(self.__variant, attr, missing)
            if value is missing:
                raise

            return value

    def _attr_error(self, attr):
        raise AttributeError("package %s has no attribute '%s'"
                             % (str(self), attr))

    def __str__(self):
        return self.__variant.qualified_package_name


class VariantsBinding(Binding):
    """Binds a list of packages.Variant objects, under the package name of
    each variant."""
    def __init__(self, variants):
        self.__variants = dict((x.name, VariantBinding(x)) for x in variants)
        super(VariantsBinding, self).__init__(self.__variants)

    def _attr_error(self, attr):
        raise AttributeError("package does not exist: '%s'" % attr)

    def __contains__(self, name):
        return (name in self.__variants)

    def __iter__(self):
        """Support for `for res in resolve`"""
        for req in self.__variants:
            yield req


class RequirementsBinding(Binding):
    """Binds a list of version.Requirement objects."""
    def __init__(self, requirements):
        self.__requirements = dict((x.name, str(x)) for x in requirements)
        super(RequirementsBinding, self).__init__(self.__requirements)

    def _attr_error(self, attr):
        raise AttributeError("request does not exist: '%s'" % attr)

    def __getitem__(self, name):
        if name in self.__requirements:
            return self.__requirements[name]
        else:
            self._attr_error(name)

    def __contains__(self, name):
        """Support for `if req in request`"""
        return (name in self.__requirements)

    def __iter__(self):
        """Support for `for req in request`"""
        for req in self.__requirements:
            yield req


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
