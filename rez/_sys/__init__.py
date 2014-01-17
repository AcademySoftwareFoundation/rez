import sys
import os
import os.path


def _forward_script(cmd=None):
    from rez.util import get_script_path
    rezolve_exe = os.path.join(get_script_path(), "rezolve")
    args = ["rezolve"] + ([cmd] if cmd else []) + sys.argv[1:]
    os.execve(rezolve_exe, args, os.environ)
