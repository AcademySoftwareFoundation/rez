"""
This sourcefile is intended to only be imported in package.py files, in
functions including:

- the special 'preprocess' function;
- early bound functions that use the @early decorator.

An example of use:

    # in package.py
    name = 'mypackage'

    version = '1.2.3'

    @early()
    def requires():
        from rez.package_py_utils import expand_requires

        return expand_requires(
            'boost-1.*.*',
            'maya-2017.*'
        )
"""

# Here to allow 'from rez.package_utils import late' in package.py
from rez.utils.sourcecode import late

# Here to allow 'from rez.package_utils import InvalidPackageError' in package.py
from rez.exceptions import InvalidPackageError


def expand_requires(*requests):
    """Create an expanded requirements list.

    Given a list of requirements with optional trailing wildcards, expand each
    out to the latest package found within that range. This is useful when a
    package is compatible with a version range of a package at build time, but
    requires a stricter requirement at runtime. For example, a compiled library
    may build with many versions of boost (boost-1.*.*), but once compiled, must
    be used with the boost version that has then been linked against (1.55.0).

    Note:
        If a package is not found in the given range, it is expanded to the
        request as-is, with trailing wildcards removed.

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
    from rez.vendor.version.requirement import VersionedObject
    from rez.packages_ import get_latest_package

    result = []

    for request in requests:
        txt = request.replace('*', '_')
        obj = VersionedObject(txt)
        rank = len(obj.version)

        request_ = request
        while request_.endswith('*'):
            request_ = request_[:-2]  # consume sep + *

        package = get_latest_package(request_)

        if package is None:
            result.append(request_)
            continue

        obj.version_ = package.version.trim(rank)
        result.append(str(obj))

    return result
