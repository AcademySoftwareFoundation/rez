"""
Binds the python setuptools module as a rez package.
"""
from __future__ import absolute_import
from rez.bind import _pymodule


def bind(path, version_range=None, opts=None, parser=None):
    name = "setuptools"

    # OSX: Copying or symlinking easy_install to anywhere other than /usr/bin
    # causes this error:
    #
    # python version 2.7.5 can't run ./easy_install.  Try the alternative(s): ...
    #
    #tools = ["easy_install"]
    tools = []

    variants = _pymodule.bind(name,
                              path=path,
                              version_range=version_range,
                              pure_python=False,
                              tools=tools,
                              extra_module_names=("pkg_resources",))

    return variants
