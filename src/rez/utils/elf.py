"""
Functions that wrap readelf/patchelf utils on linux.
"""
import pipes
import subprocess

from rez.utils.filesystem import make_path_writable


def get_rpaths(elfpath):
    """Get rpaths/runpaths from header.
    """

    # stdout lines look like:
    # 0x000000000000000f (RPATH) Library rpath: [/xxx:/yyy]
    #
    out = _run("readelf", "-d", elfpath)

    # parse out rpath/runpath
    for line in out.split('\n'):
        parts = line.strip().split()
        if "(RPATH)" in parts or "(RUNPATH)" in parts:
            txt = parts[-1]
            txt = txt[1:-1]  # strip [ and ]
            rpaths = txt.split(':')

            return rpaths or []

    return []


def patch_rpaths(elfpath, rpaths):
    """Replace an elf's rpath header with those provided.

    Note that if `rpaths` is longer than the existing header, you're gonna be
    in trouble. This function doesn't protect you from doing that.
    """
    with make_path_writable(elfpath):
        _run("patchelf", "--set-rpath", ':'.join(rpaths), elfpath)


def _run(*nargs):
    proc = subprocess.Popen(nargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()

    if proc.returncode:
        cmd_ = ' '.join(pipes.quote(x) for x in nargs)

        raise RuntimeError(
            "Command %s - failed with exitcode %d: %s"
            % (cmd_, proc.returncode, err.strip().replace('\n', "\\n"))
        )

    return out
