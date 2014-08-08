import sys
import os
import os.path
import platform
import textwrap
from build_utils.virtualenv import virtualenv


_platform = platform.system().lower()


# _REZ_PYTHON_WRAPPER_PID is set so that rez ignores this process when detecting
# what the current shell type is. Someone might be using tcsh, but the python
# wrapper here could have detected bash and used that, therefore this process
# needs to be ignored when inspecting the pid stack.

patch_code = {
    "bash": """
            #!{shell_executable}
            export _REZ_PYTHON_WRAPPER_PID=$$
            $(dirname $0)/_python -E $*
            """
}


def detect_shell():
    if _platform in ("linux", "darwin"):
        for filepath in ("/bin/bash",):
            if os.path.isfile(filepath):
                return ("bash", filepath)
    return None, None


def patch_virtualenv(dest_dir):
    """Patch a virtualenv.

    This function patches a virtualenv so that it becomes standalone and ignores
    PYTHONPATH and other environment variables that might affect its python
    interpreter. This is necessary so that the Rez commandline tools can work
    correctly, even though they're used from a rez-configured environment, where
    rez packages may have modified PYTHONPATH etc.
    """

    # detect what we're on and what shell to use
    shell_type, shell_executable = detect_shell()
    if not shell_executable:
        print >> sys.stderr, \
            ("Couldn't patch virtualenv - rez command line tools may not work "
             "correctly within a rez-env'd shell, because they will be affected "
             "by PYTHONPATH etc.")
        return

    py_executable = os.path.join(dest_dir, "bin", "python")
    real_py_executable = os.path.join(dest_dir, "bin", "_python")
    os.rename(py_executable, real_py_executable)

    code = patch_code[shell_type].format(shell_executable=shell_executable)
    code = textwrap.dedent(code).strip()

    with open(py_executable, 'w') as f:
        f.write(code + '\n')

    virtualenv.make_exe(py_executable)
