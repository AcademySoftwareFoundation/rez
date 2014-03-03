import sys
import os
import os.path


def _forward_script(cmd=None):
    if cmd == 'rez':
        cmd = None
    rezolve_exe = os.path.join(os.path.dirname(sys.argv[0]), "rezolve")
    args = ["rezolve"] + ([cmd] if cmd else []) + sys.argv[1:]
    os.execve(rezolve_exe, args, os.environ)
