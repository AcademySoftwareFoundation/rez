# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import rez.deprecations
from rez.packages import *  # noqa


rez.deprecations.warn(
    "rez.packages_ is deprecated; import rez.packages instead",
    rez.deprecations.RezDeprecationWarning,
)
