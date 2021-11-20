# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
Misc useful stuff.
TODO: Move this into rez.utils.?
"""
import collections
import atexit
import os
import os.path
import re
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


_find_unsafe = re.compile(r'[^\w@%+=`:,./-]').search


def shlex_join(value, unsafe_regex=None, replacements=None,
               enclose_with='"'):
    """Join args into a valid shell command.
    """

    # historic backwards compatibility, unsure why this is here
    if not is_non_string_iterable(value):
        return str(value)

    unsafe_regex = unsafe_regex or _find_unsafe

    def escape_word(s):
        if not s:
            return "''"
        if unsafe_regex(s) is None:
            return s

        for from_, to_ in (replacements or []):
            if isinstance(from_, six.string_types):
                s = s.replace(from_, to_)
            else:
                s = from_.sub(to_, s)  # assume from_ is re.compile

        return enclose_with + s + enclose_with

    return ' '.join(escape_word(x) for x in value)


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
