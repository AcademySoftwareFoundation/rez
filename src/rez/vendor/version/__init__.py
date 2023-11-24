# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import rez.deprecations

rez.deprecations.warn(
    "module 'rez.vendor.version' is deprecated and will be removed in 3.0.0. Use 'rez.version' instead.",
    rez.deprecations.RezDeprecationWarning,
    stacklevel=2
)
