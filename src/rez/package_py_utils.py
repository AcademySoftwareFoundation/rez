"""
This sourcefile is intended to only be imported in package.py files, in
functions including:

- the special 'preprocess' function;
- early bound functions that use the @early decorator.
"""

# these imports just forward the symbols into this module's namespace
from rez.utils.sourcecode import late
from rez.exceptions import InvalidPackageError


def expand_requirement(request):
    """Expands a requirement string like 'python-2.*'

    Only trailing wildcards are supported; they will be replaced with the
    latest package version found within the range. If none are found, the
    wildcards will just be stripped.

    Example:

        >>> print expand_requirement('python-2.*')
        python-2.7

    Args:
        request (str): Request to expand, eg 'python-2.*'

    Returns:
        str: Expanded request string.
    """
    if '*' not in request:
        return request

    from rez.vendor.version.requirement import VersionedObject, Requirement
    from rez.packages_ import get_latest_package

    txt = request.replace('*', '_')
    obj = VersionedObject(txt)
    rank = len(obj.version)

    request_ = request
    while request_.endswith('*'):
        request_ = request_[:-2]  # strip sep + *

    req = Requirement(request_)
    package = get_latest_package(name=req.name, range_=req.range_)

    if package is None:
        return request_

    obj.version_ = package.version.trim(rank)
    return str(obj)


def expand_requires(*requests):
    """Create an expanded requirements list.

    Example:

        >>> print expand_requires(["boost-1.*.*"])
        ["boost-1.55.0"]
        >>> print expand_requires(["boost-1.*"])
        ["boost-1.55"]

    Args:
        requests (list of str): Requirements to expand. Each value may have
            trailing wildcards.

    Returns:
        List of str: Expanded requirements.
    """
    return [expand_requirement(x) for x in requests]
