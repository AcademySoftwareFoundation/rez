# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Custom py2/3 interoperability code.

Put any code here that deals with py2/3 interoperability, beyond simple cases
that use (for eg) the six module.
"""
import sys

from rez.vendor.six import six


def get_function_arg_names(func):
    """Get names of a function's args.

    Gives full list of positional and keyword-only (py3 only) args.
    """
    import inspect

    if hasattr(inspect, "getfullargspec"):
        spec = inspect.getfullargspec(func)
        return spec.args + spec.kwonlyargs
    else:
        return inspect.getargspec(func).args


def load_module_from_file(name, filepath):
    """Load a python module from a sourcefile.

    Args:
        name (str): Module name.
        filepath (str): Python sourcefile.

    Returns:
        `module`: Loaded module.
    """
    if six.PY2:
        import imp
        with open(filepath) as f:
            module = imp.load_source(name, filepath, f)
            # Keep the module out of sys.modules. See comment in the `else:`
            # for more info
            if name in sys.modules:
                del sys.modules[name]
            return module

    else:
        # The below code will import the module _without_ adding it to
        # sys.modules. We want this otherwise we can't import multiple
        # versions of the same module
        # See: https://github.com/AcademySoftwareFoundation/rez/issues/1483
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
