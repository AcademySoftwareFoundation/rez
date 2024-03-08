# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Misc useful stuff.
TODO: Move this into rez.utils.?
"""
import collections.abc
import atexit
import os
import os.path
import re
import inspect

from rez.exceptions import RezError
from rez.vendor.progress.bar import Bar


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
            if isinstance(from_, str):
                s = s.replace(from_, to_)
            else:
                s = from_.sub(to_, s)  # assume from_ is re.compile

        return enclose_with + s + enclose_with

    return ' '.join(escape_word(x) for x in value)


# returns path to first program in the list to be successfully found
def which(*programs, **shutilwhich_kwargs):
    from rez.utils.which import which as which_

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
    return (
        isinstance(arg, collections.abc.Iterable)
        and not isinstance(arg, str)
    )


def get_function_arg_names(func):
    """Get names of a function's args.

    Gives full list of positional and keyword-only args.
    """
    spec = inspect.getfullargspec(func)
    return spec.args + spec.kwonlyargs


def load_module_from_file(name, filepath):
    """Load a python module from a sourcefile.

    Args:
        name (str): Module name.
        filepath (str): Python sourcefile.

    Returns:
        `module`: Loaded module.
    """
    # The below code will import the module _without_ adding it to
    # sys.modules. We want this otherwise we can't import multiple
    # versions of the same module
    # See: https://github.com/AcademySoftwareFoundation/rez/issues/1483
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
