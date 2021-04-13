"""
This sourcefile is intended to be imported in package.py files, in functions
including:

- the special 'preprocess' function;
- early bound functions that use the @early decorator.
"""

# these imports just forward the symbols into this module's namespace
from rez.utils.request_directives import parse_directive
from rez.utils.execution import Popen
from rez.exceptions import InvalidPackageError
from rez.vendor.six import six


basestring = six.string_types[0]


def late_expand_requirement(request):
    """Expands a requirement string after resolve, if possible
    """
    request_ = parse_directive(request)
    # should we prompt warning when it ends up early expand ?
    return expand_requirement(request_)


def expand_requirement(request, paths=None):
    """Expands a requirement string like 'python-2.*', 'foo-2.*+<*', etc.

    Wildcards are expanded to the latest version that matches. There is also a
    special wildcard '**' that will expand to the full version, but it cannot
    be used in combination with '*'.

    Wildcards MUST placehold a whole version token, not partial - while 'foo-2.*'
    is valid, 'foo-2.v*' is not.

    Wildcards MUST appear at the end of version numbers - while 'foo-1.*.*' is
    valid, 'foo-1.*.0' is not.

    It is possible that an expansion will result in an invalid request string
    (such as 'foo-2+<2'). The appropriate exception will be raised if this
    happens.

    Examples:

        >>> print(expand_requirement('python-2.*'))
        python-2.7
        >>> print(expand_requirement('python==2.**'))
        python==2.7.12
        >>> print(expand_requirement('python<**'))
        python<3.0.5

    Args:
        request (str): Request to expand, eg 'python-2.*'
        paths (list of str, optional): paths to search for package families,
            defaults to `config.packages_path`.

    Returns:
        str: Expanded request string.
    """
    if '*' not in request:
        return request

    from rez.vendor.version.version import VersionRange
    from rez.vendor.version.requirement import Requirement
    from rez.vendor.version.util import dewildcard
    from rez.packages import get_latest_package

    with dewildcard(request) as deer:
        req = deer.victim

        def expand(version, rank):
            range_ = VersionRange(str(version))
            package = get_latest_package(name=req.name,
                                         range_=range_,
                                         paths=paths)
            if package is None:
                return version
            if rank:
                return package.version.trim(rank)
            else:
                return package.version

        deer.on_wildcard(expand)

    result = str(req)

    # do some cleanup so that long uids aren't left in invalid wildcarded strings
    result = deer.restore(result)

    # cast back to a Requirement again, then back to a string. This will catch
    # bad verison ranges, but will also put OR'd version ranges into the correct
    # order
    expanded_req = Requirement(result)

    return str(expanded_req)


def expand_requires(*requests):
    """Create an expanded requirements list.

    Example:

        >>> print(expand_requires(["boost-1.*.*"]))
        ["boost-1.55.0"]
        >>> print(expand_requires(["boost-1.*"]))
        ["boost-1.55"]

    Args:
        requests (list of str): Requirements to expand. Each value may have
            trailing wildcards.

    Returns:
        List of str: Expanded requirements.
    """
    return [expand_requirement(x) for x in requests]


def exec_command(attr, cmd):
    """Runs a subproc to calculate a package attribute.
    """
    import subprocess

    p = Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()

    if p.returncode:
        from rez.exceptions import InvalidPackageError
        raise InvalidPackageError(
            "Error determining package attribute '%s':\n%s" % (attr, err))

    return out.strip(), err.strip()


def exec_python(attr, src, executable="python"):
    """Runs a python subproc to calculate a package attribute.

    Args:
        attr (str): Name of package attribute being created.
        src (list of str): Python code to execute, will be converted into
            semicolon-delimited single line of code.

    Returns:
        str: Output of python process.
    """
    import subprocess

    if isinstance(src, basestring):
        src = [src]

    p = Popen([executable, "-c", "; ".join(src)],
              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()

    if p.returncode:
        from rez.exceptions import InvalidPackageError
        raise InvalidPackageError(
            "Error determining package attribute '%s':\n%s" % (attr, err))

    return out.strip()


def find_site_python(module_name, paths=None):
    """Find the rez native python package that contains the given module.

    This function is used by python 'native' rez installers to find the native
    rez python package that represents the python installation that this module
    is installed into.

    Note:
        This function is dependent on the behavior found in the python '_native'
        package found in the 'rez-recipes' repository. Specifically, it expects
        to find a python package with a '_site_paths' list attribute listing
        the site directories associated with the python installation.

    Args:
        module_name (str): Target python module.
        paths (list of str, optional): paths to search for packages,
            defaults to `config.packages_path`.

    Returns:
        `Package`: Native python package containing the named module.
    """
    from rez.packages import iter_packages
    import subprocess
    import ast
    import os

    py_cmd = 'import {x}; print({x}.__path__)'.format(x=module_name)

    p = Popen(
        ["python", "-c", py_cmd], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True
    )
    out, err = p.communicate()

    if p.returncode:
        raise InvalidPackageError(
            "Failed to find installed python module '%s':\n%s"
            % (module_name, err))

    module_paths = ast.literal_eval(out.strip())

    def issubdir(path, parent_path):
        return path.startswith(parent_path + os.sep)

    for package in iter_packages("python", paths=paths):
        if not hasattr(package, "_site_paths"):
            continue

        contained = True

        for module_path in module_paths:
            if not any(issubdir(module_path, x) for x in package._site_paths):
                contained = False

        if contained:
            return package

    raise InvalidPackageError(
        "Failed to find python installation containing the module '%s'. Has "
        "python been installed as a rez package?" % module_name)
