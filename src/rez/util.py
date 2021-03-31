"""
Misc useful stuff.
TODO: Move this into rez.utils.?
"""
import collections
import atexit
import os
import os.path
from rez.exceptions import RezError
from rez.vendor.progress.bar import Bar
from rez.vendor.six import six


class ProgressBar(Bar):
    def __init__(self, label, max):
        from rez.config import config

        if config.quiet or not config.show_progress:
            self.file = open(os.devnull, 'w')
            self.close_file = True
            self.hide_cursor = False
        else:
            self.close_file = False

        super(Bar, self).__init__(label, max=max, bar_prefix=' [', bar_suffix='] ')

    def __del__(self):
        if self.close_file:
            self.file.close()
        if hasattr(Bar, '__del__'):
            Bar.__del__(self)


def dedup(seq):
    """Remove duplicates from a list while keeping order."""
    seen = set()
    for item in seq:
        if item not in seen:
            seen.add(item)
            yield item


def shlex_join(value):
    import pipes

    def quote(s):
        return pipes.quote(s) if '$' not in s else s

    if is_non_string_iterable(value):
        return ' '.join(quote(x) for x in value)
    else:
        return str(value)


# returns path to first program in the list to be successfully found
def which(*programs, **shutilwhich_kwargs):
    from rez.backport.shutilwhich import which as which_
    for prog in programs:
        path = which_(prog, **shutilwhich_kwargs)
        if path:
            return path
    return None


# case-insensitive fuzzy string match
def get_close_matches(term, fields, fuzziness=0.4, key=None):
    import math
    import difflib

    def _ratio(a, b):
        return difflib.SequenceMatcher(None, a, b).ratio()

    term = term.lower()
    matches = []

    for field in fields:
        fld = field if key is None else key(field)
        if term == fld:
            matches.append((field, 1.0))
        else:
            name = fld.lower()
            r = _ratio(term, name)
            if name.startswith(term):
                r = math.pow(r, 0.3)
            elif term in name:
                r = math.pow(r, 0.5)
            if r >= (1.0 - fuzziness):
                matches.append((field, min(r, 0.99)))

    return sorted(matches, key=lambda x: -x[1])


# fuzzy string matching on package names, such as 'boost', 'numpy-3.4'
def get_close_pkgs(pkg, pkgs, fuzziness=0.4):
    matches = get_close_matches(pkg, pkgs, fuzziness=fuzziness)
    fam_matches = get_close_matches(pkg.split('-')[0], pkgs,
                                    fuzziness=fuzziness,
                                    key=lambda x: x.split('-')[0])

    d = {}
    for pkg_, r in (matches + fam_matches):
        d[pkg_] = d.get(pkg_, 0.0) + r

    combined = [(k, v * 0.5) for k, v in d.items()]
    return sorted(combined, key=lambda x: -x[1])


def find_last_sublist(list_, sublist):
    """Given a list, find the last occurance of a sublist within it.

    Returns:
        Index where the sublist starts, or None if there is no match.
    """
    for i in reversed(range(len(list_) - len(sublist) + 1)):
        if list_[i] == sublist[0] and list_[i:i + len(sublist)] == sublist:
            return i
    return None


@atexit.register
def _atexit():
    try:
        from rez.resolved_context import ResolvedContext
        ResolvedContext.tmpdir_manager.clear()
    except RezError:
        pass


def is_non_string_iterable(arg):
    """Python 2 and 3 compatible non-string iterable identifier"""

    if six.PY2:
        iterable_class = collections.Iterable
    else:
        iterable_class = collections.abc.Iterable

    return (
        isinstance(arg, iterable_class)
        and not isinstance(arg, six.string_types)
    )

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
