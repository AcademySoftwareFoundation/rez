"""
Exceptions.
"""
from rez.exceptions import RezError
from rez.vendor.enum import Enum


class ErrorCode(Enum):
    """Program exit codes."""
    # A rez environment for a wrapped tool failed to resolve
    failed_wrapper_resolve = 111
    # A soma wrapper was run that has no matching profile present
    tool_missing_profile = 112
    # An invalid file commit handle was used on a profile
    no_such_file_handle = 113


class SomaError(RezError):
    """Base class for all soma errors."""
    pass


class SomaNotFoundError(SomaError):
    """A resource was not found."""
    pass


class SomaDataError(SomaError):
    """Invalid config data was read."""
    pass
