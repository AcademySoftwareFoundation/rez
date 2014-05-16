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

    def __attr_error(self, attr):
        raise NotImplemented

    def __getattr__(self, attr):
        try:
            return self.__data[attr]
        except KeyError:
            self.__attr_error(attr)


class VersionBinding(Binding):
    """Binds a version.Version object."""
    def __init__(self, version):
        super(VersionBinding,self).__init__()
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

    def __attr_error(self, attr):
        raise AttributeError("version object has no attribute '%s'" % attr)

    def __getitem__(self, i):
        try:
            s = str(self.__version[i])
        except IndexError:
            return ""
        if s.isdigit() and s[0] != '0':
            return int(s)
        else:
            return s

    def __len__(self):
        return len(self.__version)

    def __str__(self):
        return str(self.__version)


class VariantBinding(Binding):
    """Binds a packages.Variant object."""
    def __init__(self, variant):
        doc = dict(
            base=variant.base,
            root=variant.root,
            version=VersionBinding(variant.version))
        super(VariantBinding,self).__init__(doc)
        self.__variant = variant

    def __attr_error(self, attr):
        raise AttributeError("package object has no attribute '%s'" % attr)

    def __str__(self):
        return self.__variant.qualified_package_name


class VariantsBinding(Binding):
    """Binds a list of packages.Variant objects, under the package name of
    each variant."""
    def __init__(self, variants):
        self.__variants = dict((x.name, VariantBinding(x)) for x in variants)
        super(VariantsBinding,self).__init__(self.__variants)

    def __attr_error(self, attr):
        raise AttributeError("package does not exist: '%s'" % attr)

    def __contains__(self, name):
        return (name in self.__variants)


class RequirementsBinding(Binding):
    """Binds a list of version.Requirement objects."""
    def __init__(self, requirements):
        self.__requirements = dict((x.name, str(x)) for x in requirements)
        super(RequirementsBinding,self).__init__(self.__requirements)

    def __attr_error(self, attr):
        raise AttributeError("request does not exist: '%s'" % attr)

    def __contains__(self, name):
        return (name in self.__requirements)
