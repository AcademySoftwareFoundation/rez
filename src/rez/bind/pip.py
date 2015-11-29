"""
Binds the python pip module as a rez package.
"""
from __future__ import absolute_import
from rez.bind import _pymodule


def bind(path, version_range=None, opts=None, parser=None):
    name = "pip"
    tools = ["pip"]

    variants = _pymodule.bind(name,
                              path=path,
                              version_range=version_range,
                              pure_python=False,
                              tools=tools)

    return variants
