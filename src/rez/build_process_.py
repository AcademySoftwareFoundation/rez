# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import rez.deprecations
from rez.build_process import *  # noqa


rez.deprecations.warn(
    "rez.build_process_ is deprecated; import rez.build_process instead",
    rez.deprecations.RezDeprecationWarning,
)
