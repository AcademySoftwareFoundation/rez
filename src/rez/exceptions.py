"""
Exceptions.
"""


class RezError(Exception):
    """Base-class Rez error."""
    def __init__(self, value=None):
        self.value = value

    def __str__(self):
        return str(self.value)


class RezSystemError(RezError):
    """Rez system/internal error."""
    pass


class RezBindError(RezError):
    """A bind-related error."""
    pass


class RezPluginError(RezError):
    """An error related to plugin or plugin load."""
    pass


class ConfigurationError(RezError):
    """A misconfiguration error."""
    pass


class ResolveError(RezError):
    """A resolve-related error."""
    pass


class PackageFamilyNotFoundError(RezError):
    """A package could not be found on disk."""
    pass


class PackageNotFoundError(RezError):
    """A package could not be found on disk."""
    pass


class ResourceError(RezError):
    """Resource-related exception base class."""
    pass


class ResourceNotFoundError(ResourceError):
    """A resource could not be found."""
    pass


class ResourceContentError(ResourceError):
    """A resource contains incorrect data."""
    type_name = "resource file"

    def __init__(self, value=None, path=None, resource_key=None):
        msg = []
        if resource_key is not None:
            msg.append("resource type: %r" % resource_key)
        if path is not None:
            msg.append("%s: %s" % (self.type_name, path))
        if value is not None:
            msg.append(value)
        ResourceError.__init__(self, ": ".join(msg))


class PackageMetadataError(ResourceContentError):
    """There is an error in a package's definition file."""
    type_name = "package definition file"


class PackageCommandError(RezError):
    """There is an error in a command or list of commands"""
    pass


class RexError(RezError):
    """There is an error in Rex code."""
    pass


class RexUndefinedVariableError(RexError):
    """There is a reference to an undefined variable."""
    pass


class BuildError(RezError):
    """Base class for any build-related error."""
    pass


class BuildSystemError(BuildError):
    """Base class for buildsys-related errors."""
    pass


class ReleaseError(RezError):
    """Any release-related error."""
    pass


class ReleaseVCSError(ReleaseError):
    """Base class for release VCS-related errors."""
    pass


class ReleaseVCSUnsupportedError(ReleaseVCSError):
    """
    Raise this error during initialization of a ReleaseVCS sub-class to
    indicate that the mode is unsupported in the given context.
    """
    pass


class ReleaseHookError(RezError):
    """Base class for release-hook- related errors."""
    pass






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
