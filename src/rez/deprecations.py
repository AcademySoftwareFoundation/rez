# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import warnings


def warn(message, category, pre_formatted=False, stacklevel=1, filename=None, **kwargs):
    """
    Wrapper around warnings.warn that allows to pass a pre-formatter
    warning message. This allows to warn about things that aren't coming
    from python files, like environment variables, etc.
    """
    if not pre_formatted:
        warnings.warn(
            message, category=category, stacklevel=stacklevel + 1, **kwargs
        )
        return

    original_formatwarning = warnings.formatwarning
    if pre_formatted:

        def formatwarning(_, category, *args, **kwargs) -> str:
            return "{0}{1}: {2}\n".format(
                "{0}: ".format(filename) if filename else "", category.__name__, message
            )

        warnings.formatwarning = formatwarning

    warnings.warn(message, category=category, stacklevel=stacklevel + 1, **kwargs)
    warnings.formatwarning = original_formatwarning


class RezDeprecationWarning(DeprecationWarning):
    pass
