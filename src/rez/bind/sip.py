"""
Binds the python PyQt module as a rez package.
"""
from __future__ import absolute_import
from rez.bind import _pymodule
from rez.bind._utils import get_version_in_python


def bind(path, version_range=None, opts=None, parser=None):
    name = "sip"

    version = get_version_in_python(
        name,
        ["import sip",
         "print(sip.SIP_VERSION_STR)"])

    variants = _pymodule.bind(name,
                              path=path,
                              version_range=version_range,
                              version=version,
                              pure_python=False)

    return variants
