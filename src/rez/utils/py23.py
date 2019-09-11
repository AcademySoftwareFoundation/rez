"""
Custom py2/3 interoperability code.

Put any code here that deals with py2/3 interoperability, beyond simple cases
that use (for eg) the six module.
"""

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
