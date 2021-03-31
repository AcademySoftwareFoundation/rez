from rez.vendor.version.requirement import Requirement


def get_patched_request(requires, patchlist):
    """Apply patch args to a request.

    For example, consider:

        >>> print(get_patched_request(["foo-5", "bah-8.1"], ["foo-6"]))
        ["foo-6", "bah-8.1"]
        >>> print(get_patched_request(["foo-5", "bah-8.1"], ["^bah"]))
        ["foo-5"]

    The following rules apply wrt how normal/conflict/weak patches override
    (note though that the new request is always added, even if it doesn't
    override an existing request):

    PATCH  OVERRIDES: foo  !foo  ~foo
    -----  ---------- ---  ----  -----
    foo               Y    Y     Y
    !foo              N    N     N
    ~foo              N    N     Y
    ^foo              Y    Y     Y

    Args:
        requires (list of str or `version.Requirement`): Request.
        patchlist (list of str): List of patch requests.

    Returns:
        List of `version.Requirement`: Patched request.
    """

    # rules from table in docstring above
    rules = {
        '': (True, True, True),
        '!': (False, False, False),
        '~': (False, False, True),
        '^': (True, True, True)
    }

    requires = [Requirement(x) if not isinstance(x, Requirement) else x
                for x in requires]
    appended = []

    for patch in patchlist:
        if patch and patch[0] in ('!', '~', '^'):
            ch = patch[0]
            name = Requirement(patch[1:]).name
        else:
            ch = ''
            name = Requirement(patch).name

        rule = rules[ch]
        replaced = (ch == '^')

        for i, req in enumerate(requires):
            if req is None or req.name != name:
                continue

            if not req.conflict:
                replace = rule[0]  # foo
            elif not req.weak:
                replace = rule[1]  # !foo
            else:
                replace = rule[2]  # ~foo

            if replace:
                if replaced:
                    requires[i] = None
                else:
                    requires[i] = Requirement(patch)
                    replaced = True

        if not replaced:
            appended.append(Requirement(patch))

    result = [x for x in requires if x is not None] + appended
    return result


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
