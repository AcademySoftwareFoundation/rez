"""
Misc useful stuff.
"""
import stat
import sys
import atexit
import os
import os.path
import copy
from rez.exceptions import RezError
from rez.utils.yaml import dump_yaml
from rez.vendor.progress.bar import Bar


DEV_NULL = open(os.devnull, 'w')

"""
class _Missing:
    pass
_missing = _Missing()
"""


class ProgressBar(Bar):
    def __init__(self, label, max):
        from rez.config import config
        if config.quiet or not config.show_progress:
            self.file = DEV_NULL
            self.hide_cursor = False

        super(Bar, self).__init__(label, max=max, bar_prefix=' [', bar_suffix='] ')


# TODO: use distlib.ScriptMaker
# TODO: or, do the work ourselves to make this cross platform
# FIXME: *nix only
def create_executable_script(filepath, body, program=None):
    """Create an executable script.

    Args:
        filepath (str): File to create.
        body (str or callable): Contents of the script. If a callable, its code
            is used as the script body.
        program (str): Name of program to launch the script, 'python' if None
    """
    program = program or "python"
    if callable(body):
        from rez.utils.sourcecode import SourceCode
        code = SourceCode(func=body)
        body = code.source

    if not body.endswith('\n'):
        body += '\n'

    with open(filepath, 'w') as f:
        # TODO: make cross platform
        f.write("#!/usr/bin/env %s\n" % program)
        f.write(body)

    # TODO: Although Windows supports os.chmod you can only set the readonly
    # flag. Setting the file readonly breaks the unit tests that expect to
    # clean up the files once the test has run.  Temporarily we don't bother
    # setting the permissions, but this will need to change.
    if os.name == "posix":
    	os.chmod(filepath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
             | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def create_forwarding_script(filepath, module, func_name, *nargs, **kwargs):
    """Create a 'forwarding' script.

    A forwarding script is one that executes some arbitrary Rez function. This
    is used internally by Rez to dynamically create a script that uses Rez,
    even though the parent environment may not be configured to do so.
    """
    doc = dict(
        module=module,
        func_name=func_name)

    if nargs:
        doc["nargs"] = nargs
    if kwargs:
        doc["kwargs"] = kwargs

    body = dump_yaml(doc)
    create_executable_script(filepath, body, "_rez_fwd")


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

    if hasattr(value, '__iter__'):
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

    combined = [(k, v * 0.5) for k, v in d.iteritems()]
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


def deep_update(dict1, dict2):
    """Perform a deep merge of `dict2` into `dict1`.

    Note that `dict2` and any nested dicts are unchanged.
    """
    for k, v in dict2.iteritems():
        if k.endswith(('.before', '.after')):
            k, suffix = k.rsplit('.', 1)
            if k not in dict1 or dict1[k] is None:
                dict1[k] = copy.deepcopy(v)
            else:
                if suffix == 'before':
                    dict1[k] = copy.deepcopy(v) + dict1[k]
                else:
                    dict1[k] = dict1[k] + copy.deepcopy(v)
        elif k in dict1 and isinstance(v, dict) and isinstance(dict1[k], dict):
            deep_update(dict1[k], v)
        else:
            dict1[k] = copy.deepcopy(v)


@atexit.register
def _atexit():
    try:
        from rez.resolved_context import ResolvedContext
        ResolvedContext.tmpdir_manager.clear()
    except RezError:
        pass


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
