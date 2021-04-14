"""
Utilities related to process/script execution.
"""

from rez.vendor.six import six
from rez.utils.yaml import dump_yaml
from rez.vendor.enum import Enum
from contextlib import contextmanager
from io import UnsupportedOperation
import subprocess
import sys
import stat
import os


@contextmanager
def add_sys_paths(paths):
    """Add to sys.path, and revert on scope exit.
    """
    original_syspath = sys.path[:]
    sys.path.extend(paths)

    try:
        yield
    finally:
        sys.path = original_syspath


if six.PY2:
    class _PopenBase(subprocess.Popen):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, value, traceback):
            self.wait()

else:  # py3
    _PopenBase = subprocess.Popen


class Popen(_PopenBase):
    """subprocess.Popen wrapper.

    Allows for Popen to be used as a context in both py2 and py3.
    """
    def __init__(self, args, **kwargs):
        # Avoids python bug described here: https://bugs.python.org/issue3905.
        # This can arise when apps (maya) install a non-standard stdin handler.
        #
        # In newer version of maya and katana, the sys.stdin object can also
        # become replaced by an object with no 'fileno' attribute, this is also
        # taken into account.
        #
        if "stdin" not in kwargs:
            try:
                file_no = sys.stdin.fileno()
            except (
                AttributeError,
                UnsupportedOperation  # https://github.com/nerdvegas/rez/pull/966
            ):
                file_no = sys.__stdin__.fileno()

            if file_no not in (0, 1, 2):
                kwargs["stdin"] = subprocess.PIPE

        # Add support for the new py3 "text" arg, which is equivalent to
        # "universal_newlines".
        # https://docs.python.org/3/library/subprocess.html#frequently-used-arguments
        #
        text = kwargs.pop("text", None)
        universal_newlines = kwargs.pop("universal_newlines", None)

        if text or universal_newlines:
            kwargs["universal_newlines"] = True

            # fixes py3/cmd.exe UnicodeDecodeError() with some characters.
            #    UnicodeDecodeError: 'charmap' codec can't decode byte
            #    0x8d in position 1023172: character maps to <undefined>
            #
            # NOTE: currently no solution for `python3+<3.6`
            #
            if sys.version_info[:2] >= (3, 6) and "encoding" not in kwargs:
                kwargs["encoding"] = "utf-8"

        super(Popen, self).__init__(args, **kwargs)


class ExecutableScriptMode(Enum):
    """
    Which scripts to create with util.create_executable_script.
    """
    # Start with 1 to not collide with None checks

    # Requested script only. Usually extension-less.
    single = 1

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

    # https://github.com/nerdvegas/rez/pull/968
    is_forwarding_script_on_windows = (
        program == "_rez_fwd"
        and platform_.name == "windows"
        and filepath.lower().endswith(".cmd")
    )

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
    # In order for execution to work in windows we need to create a .py
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
            if is_forwarding_script_on_windows:
                # following lines of batch script will be stripped
                # before yaml.load
                f.write("@echo off\n")
                f.write("%s.exe %%~dpnx0 %%*\n" % program)
                f.write("goto :eof\n")  # skip YAML body
                f.write(":: YAML\n")    # comment for human
            else:
                f.write("#!/usr/bin/env %s\n" % program)

            f.write(body)

        # TODO: Although Windows supports os.chmod you can only set the readonly
        # flag. Setting the file readonly breaks the unit tests that expect to
        # clean up the files once the test has run.  Temporarily we don't bother
        # setting the permissions, but this will need to change.
        if os.name == "posix":
            os.chmod(
                current_filepath,
                stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IXUSR
                | stat.S_IXGRP | stat.S_IXOTH
            )

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
        list of str: filepaths of scripts to create based on inputs

    """
    script_filepaths = []
    base_filepath, extension = os.path.splitext(filepath)
    has_py_ext = extension == ".py"
    is_windows = platform == "windows"

    if (
        py_script_mode == ExecutableScriptMode.single
        or py_script_mode == ExecutableScriptMode.both
        or (py_script_mode == ExecutableScriptMode.py and has_py_ext)
        or (py_script_mode == ExecutableScriptMode.platform_specific and not is_windows)
        or (py_script_mode == ExecutableScriptMode.platform_specific and is_windows and has_py_ext)
    ):
        script_filepaths.append(filepath)

    if (
        not has_py_ext
        and (
            py_script_mode == ExecutableScriptMode.both
            or py_script_mode == ExecutableScriptMode.py
            or (py_script_mode == ExecutableScriptMode.platform_specific and is_windows)
        )
    ):
        script_filepaths.append(base_filepath + ".py")

    return script_filepaths


def create_forwarding_script(filepath, module, func_name, *nargs, **kwargs):
    """Create a 'forwarding' script.

    A forwarding script is one that executes some arbitrary Rez function. This
    is used internally by Rez to dynamically create a script that uses Rez,
    even though the parent environment may not be configured to do so.
    """
    from rez.utils.platform_ import platform_

    if platform_.name == "windows" and \
            os.path.splitext(filepath)[-1].lower() != ".cmd":
        filepath += ".cmd"

    doc = dict(
        module=module,
        func_name=func_name)

    if nargs:
        doc["nargs"] = nargs
    if kwargs:
        doc["kwargs"] = kwargs

    body = dump_yaml(doc)
    create_executable_script(filepath, body, "_rez_fwd")
