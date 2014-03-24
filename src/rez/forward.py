import json
import stat
import os



def create_forwarding_script(filepath, module, func_name, shell=None,
                             *nargs, **kwargs):
    """Create a 'forwarding' script.

    A forwarding script is one that executes some arbitrary Rez function. This
    is used internally by Rez to dynamically create a script that uses Rez, even
    though the parent environ may not be configured to do so. The cmake build
    system uses this, to create its 'build-env' scripts.

    The target function that this script forwards to must contain the kwargs
    '_script' (path to the forwarding script), and '_cli_args' (list of command
    line arguments passed to the forwarding script).
    """
    code = textwrap.dedent(\
        """
        import sys
        import os

        # backported from python 3
        def which(cmd, mode=os.F_OK | os.X_OK, path=None):
            def _access_check(fn, mode):
                return (os.path.exists(fn) and os.access(fn, mode)
                        and not os.path.isdir(fn))
            if _access_check(cmd, mode):
                return cmd

            path = (path or os.environ.get("PATH", os.defpath)).split(os.pathsep)
            if sys.platform == "win32":
                if not os.curdir in path:
                    path.insert(0, os.curdir)
                pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
                matches = [cmd for ext in pathext if cmd.lower().endswith(ext.lower())]
                files = [cmd] if matches else [cmd + ext.lower() for ext in pathext]
            else:
                files = [cmd]

            seen = set()
            for dir in path:
                dir = os.path.normcase(dir)
                if not dir in seen:
                    seen.add(dir)
                    for thefile in files:
                        name = os.path.join(dir, thefile)
                        if _access_check(name, mode):
                            return name
            return None

        rezolve_exe = which("rezolve")
        if not rezolve_exe:
            raise RuntimeError("cannot see 'rezolve' executable")

        nargs = %(nargs)s
        kwargs = %(kwargs)s
        kwargs["_script"] = sys.argv[0]
        kwargs["_cli_args"] = sys.argv[1:]
        data = [nargs, kwargs]
        data_s = json.dumps(data)

        cmd = ["rezolve", "forward", module, func_name, data_s]
        os.execve(rezolve_exe, cmd, os.environ)
        """) % dict(nargs=str(nargs), kwargs=str(kwargs))

    with open(filepath, 'w') as f:
        f.write(code)

    os.chmod(filepath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH \
        | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
