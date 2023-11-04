# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import rez.deprecations
from rez.package_maker import *  # noqa


rez.deprecations.warn(
    "rez.package_maker__ is deprecated; import rez.package_maker instead",
    rez.deprecations.RezDeprecationWarning,
)
