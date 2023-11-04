# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import rez.deprecations
from rez.package_resources import *  # noqa


rez.deprecations.warn(
    "rez.package_resources_ is deprecated; import rez.package_resources instead",
    rez.deprecations.RezDeprecationWarning,
)
