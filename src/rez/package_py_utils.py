"""
This sourcefile is intended to be imported in package.py files, in functions
including:

- the special 'preprocess' function;
- early bound functions that use the @early decorator.
"""

# these imports just forward the symbols into this module's namespace
from rez.utils.sourcecode import late
from rez.exceptions import InvalidPackageError


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

        >>> print expand_requirement('python-2.*')
        python-2.7
        >>> print expand_requirement('python==2.**')
        python==2.7.12
        >>> print expand_requirement('python<**')
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
    from rez.packages_ import get_latest_package
    from uuid import uuid4

    wildcard_map = {}
    expanded_versions = {}
    request_ = request

    # replace wildcards with valid version tokens that can be replaced again
    # afterwards. This produces a horrendous, but both valid and temporary,
    # version string.
    #
    while "**" in request_:
        uid = "_%s_" % uuid4().hex
        request_ = request_.replace("**", uid, 1)
        wildcard_map[uid] = "**"

    while '*' in request_:
        uid = "_%s_" % uuid4().hex
        request_ = request_.replace('*', uid, 1)
        wildcard_map[uid] = '*'

    # create the requirement, then expand wildcards
    #
    req = Requirement(request_, invalid_bound_error=False)

    def expand_version(version):
        rank = len(version)
        wildcard_found = False

        while version and str(version[-1]) in wildcard_map:
            token = wildcard_map[str(version[-1])]
            version = version.trim(len(version) - 1)

            if token == "**":
                if wildcard_found:  # catches bad syntax '**.*'
                    return None
                else:
                    wildcard_found = True
                    rank = 0
                    break

            wildcard_found = True

        if not wildcard_found:
            return None

        range_ = VersionRange(str(version))
        package = get_latest_package(name=req.name, range_=range_, paths=paths)

        if package is None:
            return version

        if rank:
            return package.version.trim(rank)
        else:
            return package.version

    def visit_version(version):
        # requirements like 'foo-1' are actually represented internally as
        # 'foo-1+<1_' - '1_' is the next possible version after '1'. So we have
        # to detect this case and remap the uid-ified wildcard back here too.
        #
        for v, expanded_v in expanded_versions.iteritems():
            if version == v.next():
                return expanded_v.next()

        version_ = expand_version(version)
        if version_ is None:
            return None

        expanded_versions[version] = version_
        return version_

    if req.range_ is not None:
        req.range_.visit_versions(visit_version)

    result = str(req)

    # do some cleanup so that long uids aren't left in invalid wildcarded strings
    for uid, token in wildcard_map.iteritems():
        result = result.replace(uid, token)

    # cast back to a Requirement again, then back to a string. This will catch
    # bad verison ranges, but will also put OR'd version ranges into the correct
    # order
    expanded_req = Requirement(result)

    return str(expanded_req)


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
