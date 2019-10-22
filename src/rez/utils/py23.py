"""
Custom py2/3 interoperability code.

Put any code here that deals with py2/3 interoperability, beyond simple cases
that use (for eg) the six module.
"""
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
            return imp.load_source(name, filepath, f)

    else:
        from importlib.machinery import SourceFileLoader
        return SourceFileLoader(name, filepath).load_module()
