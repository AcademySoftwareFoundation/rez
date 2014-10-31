"""
Exceptions.
"""
from rez.exceptions import RezError


class SomaError(RezError):
    """Base class for all soma errors."""
    pass


class SomaNotFoundError(SomaError):
    """A resource was not found."""
    pass
