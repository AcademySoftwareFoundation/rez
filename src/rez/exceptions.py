# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
Exceptions.
"""
from contextlib import contextmanager


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


class PackageRequestError(RezError):
    """There is an error related to a package request."""
    pass


class PackageCopyError(RezError):
    """There was a problem copying a package."""
    pass


class PackageMoveError(RezError):
    """There was a problem moving a package."""
    pass


class ContextBundleError(RezError):
    """There was a problem bundling a context."""
    pass


class PackageCacheError(RezError):
    """There was an error related to a package cache."""
    pass


class PackageTestError(RezError):
    """There was a problem running a package test."""
    pass


class ResolvedContextError(RezError):
    """An error occurred in a resolved context."""
    pass


class RexError(RezError):
    """There is an error in Rex code."""
    pass


class RexUndefinedVariableError(RexError):
    """There is a reference to an undefined variable."""
    pass


class RexStopError(RexError):
    """Special error raised when a package commands uses the 'stop' command."""
    pass


class BuildError(RezError):
    """Base class for any build-related error."""
    pass


class BuildSystemError(BuildError):
    """Base class for buildsys-related errors."""
    pass


class BuildContextResolveError(BuildError):
    """Raised if unable to resolve the required context when creating the
    environment for a build process."""
    def __init__(self, context):
        self.context = context
        assert context.status != "solved"
        msg = ("The build environment could not be resolved:\n%s"
               % context.failure_description)
        super(BuildContextResolveError, self).__init__(msg)


class BuildProcessError(RezError):
    """Base class for build process-related errors."""
    pass


class ReleaseError(RezError):
    """Any release-related error."""
    pass


class ReleaseVCSError(ReleaseError):
    """Base class for release VCS-related errors."""
    pass


class ReleaseHookError(RezError):
    """Base class for release-hook- related errors."""
    pass


class ReleaseHookCancellingError(RezError):
    """A release hook error that asks to cancel the release as a result."""
    pass


class SuiteError(RezError):
    """Any suite-related error."""
    pass


class PackageRepositoryError(RezError):
    """Base class for package repository- related errors."""
    pass


class InvalidPackageError(RezError):
    """A special case exception used in package 'preprocess function'."""
    pass


class RezGuiQTImportError(ImportError):
    """A special case - see cli/gui.py
    """
    pass


class _NeverError(RezError):
    """Exception that is never raised.

    Used to toggle exception handling in some cases.
    """
    pass


@contextmanager
def convert_errors(from_, to, msg=None):
    exc = None

    try:
        yield None
    except from_ as e:
        exc = e

    if exc:
        info = "%s: %s" % (exc.__class__.__name__, str(exc))
        if msg:
            info = "%s: %s" % (msg, info)
        raise to(info)
