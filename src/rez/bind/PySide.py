# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Binds the python PySide module as a rez package.
"""
from rez.bind import _pymodule


def bind(path, version_range=None, opts=None, parser=None):
    name = "PySide"
    tools = ["pyuic4"]

    variants = _pymodule.bind(name,
                              path=path,
                              version_range=version_range,
                              pure_python=False,
                              tools=tools)

    return variants
