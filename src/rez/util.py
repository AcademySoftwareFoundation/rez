"""
Misc useful stuff.
"""
import stat
import sys
import collections
import atexit
import os
import os.path
import copy
from rez.exceptions import RezError
from rez.utils.yaml import dump_yaml
from rez.vendor.progress.bar import Bar
from rez.vendor.enum import Enum
from rez.vendor.six import six

DEV_NULL = open(os.devnull, 'w')


class ExecutableScriptMode(Enum):
    """
    Which scripts to create with util.create_executable_script.
    """
    # Start with 1 to not collide with None checks

    # Requested shebang script only. Usually extension-less.
    requested = 1

    # Create .py script that will allow launching scripts on
    # windows without extension, but may require extension on
    # other systems.
    py = 2

    # Will create py script on windows and requested on
    # other platforms
    platform_specific = 3

    # Creates the requested script and an .py script so that scripts
    # can be launched without extension from windows and other
    # systems.
    both = 4


class ProgressBar(Bar):
    def __init__(self, label, max):
        from rez.config import config
        if config.quiet or not config.show_progress:
            self.file = DEV_NULL
            self.hide_cursor = False

        super(Bar, self).__init__(label, max=max, bar_prefix=' [', bar_suffix='] ')


# TODO: Maybe also allow distlib.ScriptMaker instead of the .py + PATHEXT.
def create_executable_script(filepath, body, program=None, py_script_mode=None):
    """
    Create an executable script. In case a py_script_mode has been set to create
    a .py script the shell is expected to have the PATHEXT environment
    variable to include ".PY" in order to properly launch the command without
    the .py extension.

    Args:
        filepath (str): File to create.
        body (str or callable): Contents of the script. If a callable, its code
            is used as the script body.
        program (str): Name of program to launch the script. Default is 'python'
        py_script_mode(ExecutableScriptMode): What kind of script to create.
            Defaults to rezconfig.create_executable_script_mode.
    Returns:
        List of filepaths of created scripts. This may differ from the supplied
        filepath depending on the py_script_mode

    """
    from rez.config import config
    from rez.utils.platform_ import platform_
    program = program or "python"
    py_script_mode = py_script_mode or config.create_executable_script_mode

    if callable(body):
        from rez.utils.sourcecode import SourceCode
        code = SourceCode(func=body)
        body = code.source

    if not body.endswith('\n'):
        body += '\n'

    # Windows does not support shebang, but it will run with
    # default python, or in case of later python versions 'py' that should
    # try to use sensible python interpreters depending on the shebang line.
    # Compare PEP-397.
    # In order to execution to work from windows we need to create a .py
    # file and set the PATHEXT to include .py (as done by the shell plugins)
    # So depending on the py_script_mode we might need to create more then
    # one script

    script_filepaths = [filepath]
    if program == "python":
        script_filepaths = _get_python_script_files(filepath, py_script_mode,
                                                    platform_.name)

    for current_filepath in script_filepaths:
        with open(current_filepath, 'w') as f:
            # TODO: make cross platform
            f.write("#!/usr/bin/env %s\n" % program)
            f.write(body)

        # TODO: Although Windows supports os.chmod you can only set the readonly
        # flag. Setting the file readonly breaks the unit tests that expect to
        # clean up the files once the test has run.  Temporarily we don't bother
        # setting the permissions, but this will need to change.
        if os.name == "posix":
            os.chmod(current_filepath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
                     | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return script_filepaths


def _get_python_script_files(filepath, py_script_mode, platform):
    """
    Evaluates the py_script_mode for the requested filepath on the given
    platform.

    Args:
        filepath: requested filepath
        py_script_mode (ExecutableScriptMode):
        platform (str): Platform to evaluate the script files for

    Returns:

    """
    script_filepaths = []
    base_filepath, extension = os.path.splitext(filepath)
    has_py_ext = extension == ".py"
    is_windows = platform == "windows"

    if py_script_mode == ExecutableScriptMode.requested or \
            py_script_mode == ExecutableScriptMode.both or \
            (py_script_mode == ExecutableScriptMode.py and has_py_ext) or \
            (py_script_mode == ExecutableScriptMode.platform_specific and
             not is_windows) or \
            (py_script_mode == ExecutableScriptMode.platform_specific and
             is_windows and has_py_ext):
        script_filepaths.append(filepath)

    if not has_py_ext and \
            ((py_script_mode == ExecutableScriptMode.both) or
             (py_script_mode == ExecutableScriptMode.py) or
             (py_script_mode == ExecutableScriptMode.platform_specific and
              is_windows)):
        script_filepaths.append(base_filepath + ".py")

    return script_filepaths


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
        isinstance(arg, collections.Iterable)
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
