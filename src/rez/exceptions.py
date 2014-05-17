"""
Exceptions.
Note: Every exception class can be default-constructed (ie all args default to None) because of
a serialisation issue with the exception class, see:
http://irmen.home.xs4all.nl/pyro3/troubleshooting.html
"""


class RezError(Exception):
    """Base-class Rez error."""
    def __init__(self, value=None):
        self.value = value

    def __str__(self):
        return str(self.value)


class ConfigurationError(RezError):
    """A misconfiguration error."""
    pass


class RezSystemError(RezError):
    """Rez system error."""
    pass


class RezBindError(RezError):
    """A bind-related error."""
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
    """There is a problem with a rez resource configuration."""
    pass

class PackageMetadataError(ResourceError):
    """There is an error in a package's definition file"""
    def __init__(self, filepath, value):
        msg = "Error in package definition file: %s\n%s" % (filepath, value)
        RezError.__init__(self, msg)
        self.filepath = filepath


class PackageCommandError(RezError):
    """There is an error in a command or list of commands"""
    pass


class RexError(RezError):
    """There is an error in Rex code."""
    pass


class RexUndefinedVariableError(RexError):
    """There is a reference to an undefined variable."""
    pass


class BuildSystemError(RezError):
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
