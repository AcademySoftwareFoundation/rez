from rez.vendor.version.requirement import Requirement


def get_patched_request(requires, patchlist):
    """Apply patch args to a request.

    For example, consider:

        >>> print get_patched_request(["foo-5", "bah-8.1"], ["foo-6"])
        ["foo-6", "bah-8.1"]
        >>> print get_patched_request(["foo-5", "bah-8.1"], ["^bah"])
        ["foo-5", "bah-8.1"]

    Args:
        requires (list of str or `version.Requirement`): Request.
        patchlist (list of str): List of patch requests.

    Returns:
        List of `version.Requirement`: Patched request.
    """
    reqmap = {}
    i = 0

    def _key(req):
        return (req.name, req.conflict)

    for req in requires:
        if not isinstance(req, Requirement):
            req = Requirement(req)
        reqmap[_key(req)] = (req, i)
        i += 1

    for patch_str in patchlist:
        if patch_str.startswith('^'):  # removal operator
            patch_req = Requirement(patch_str[1:])
            for b in (True, False):
                k = (patch_req.name, b)
                reqmap.pop(k, None)
            continue

        patch_req = Requirement(patch_str)
        k = _key(patch_req)
        if k in reqmap:
            _, j = reqmap[k]
            reqmap[k] = (patch_req, j)
        else:
            reqmap[k] = (patch_req, i)
            i += 1

    values = sorted(reqmap.values(), key=lambda x: x[1])
    result = [x[0] for x in values]
    return result
