# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Implements everything needed to manipulate versions and requirements.

There are three class types: :class:`VersionToken`, :class:`Version` and :class:`VersionRange`.
A :class:`Version` is a set of zero or more :class:`VersionToken`\\s, separate by ``.``\\s or ``-``\\s (eg ``1.2-3``).
A :class:`VersionToken` is a string containing alphanumerics, and default implemenations
:class:`NumericToken` and :class:`AlphanumericVersionToken` are supplied. You can implement
your own if you want stricter tokens or different sorting behaviour.

A :class:`VersionRange` is a set of one or more contiguous version ranges. For example,
``3+<5`` contains any version >=3 but less than 5. Version ranges can be used to
define dependency requirements between objects. They can be OR'd together, AND'd
and inverted.

The empty version ``''``, and empty version range ``''``, are also handled. The empty
version is used to denote unversioned objects. The empty version range, also
known as the 'any' range, is used to refer to any version of an object.

Requirements and list of requirements are represented by :class:`Requirement` and
:class:`RequirementList` respectively.
"""

from rez.version._requirement import Requirement, RequirementList, VersionedObject
from rez.version._util import ParseException, VersionError
from rez.version._version import (
    AlphanumericVersionToken,
    NumericToken,
    Version,
    VersionRange,
    VersionToken,
    reverse_sort_key,
)

__all__ = (
    "Version",
    "VersionRange",
    "Requirement",
    "RequirementList",
    "VersionedObject",
    "VersionToken",
    "NumericToken",
    "AlphanumericVersionToken",
    "reverse_sort_key",
    "ParseException",
    "VersionError",
)
