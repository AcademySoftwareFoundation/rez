"""
Binds a python executable as a rez package.
"""
from rez.package_maker_ import make_py_package, code_provider, root
from rez.exceptions import RezBindError
from rez.vendor.version.version import Version
from rez.vendor.version.requirement import VersionedObject
from rez.system import system
import subprocess
import sys


def setup_parser(parser):
    parser.add_argument("--exe", type=str, metavar="PATH",
                        help="bind an interpreter other than the current "
                        "python interpreter")


@code_provider
def commands():
    env.PATH.append('{this.root}/bin')


def bind(path, version_range=None, opts=None, parser=None):
    # get path to exe, version
    if opts and opts.exe:
        exepath = opts.exe
        p = subprocess.Popen([exepath, "-V"], stdout=subprocess.PIPE)
        stdout,_ = p.communicate()
        if p.returncode:
            raise RezBindError("failed to execute provided interpreter")

        try:
            strver = stdout.strip().split()[-1]
            toks = strver.replace('.',' ').replace('-',' ').split()
            strver = '.'.join(toks[:3])
            version = Version(strver)
        except Exception as e:
            raise RezBindError("failed to parse python version: %s" % str(e))
    else:
        exepath = sys.executable
        strver = '.'.join(str(x) for x in sys.version_info[:3])
        version = Version(strver)

    if version_range and version not in version_range:
        raise RezBindError("found version %s is not within range %s"
                           % (str(version), str(version_range)))

    with make_py_package("python", version, path) as pkg:
        pkg.add_variant(*system.variant)
        pkg.set_tools("python")
        pkg.set_commands(commands)
        pkg.add_link(exepath, root("bin", "python"))

    return ("python", version)
