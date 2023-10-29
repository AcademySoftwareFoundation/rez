# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import warnings

from rez.config import config


def warn(message, category, stacklevel=1, **kwargs):
    """
    Small wrapper around :func:`warnings.warn` that can force python to show all
    warnings if the log_all_deprecation_warnings rez setting is set to True.
    """
    if config.log_all_deprecation_warnings:
        with warnings.catch_warnings():
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")
            warnings.warn(
                message, category=category, stacklevel=stacklevel + 1, **kwargs
            )
    else:
        warnings.warn(message, category=category, stacklevel=stacklevel + 1, **kwargs)
