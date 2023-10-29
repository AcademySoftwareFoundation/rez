# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import warnings


def warn(message, category, stacklevel=1, **kwargs):
    """
    Small wrapper around :func:`warnings.warn` that can force python to show all
    warnings if the REZ_LOG_ALL_DEPRECATION_WARNINGS rez setting is set.
    """
    # Note that we use an environment variable because we can also need to do something similar
    # for the config files, from which we don't have access to any user configured configs.
    if os.getenv("REZ_LOG_ALL_DEPRECATION_WARNINGS"):
        with warnings.catch_warnings():
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")
            warnings.warn(
                message, category=category, stacklevel=stacklevel + 1, **kwargs
            )
    else:
        warnings.warn(message, category=category, stacklevel=stacklevel + 1, **kwargs)
