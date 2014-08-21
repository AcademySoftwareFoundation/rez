"""
Binds a python executable as a rez package.
"""
from rez.package_maker_ import make_py_package, code_provider, root
from rez.bind_utils import check_version, find_exe, extract_version
from rez.exceptions import RezBindError
from rez.vendor.version.version import Version
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
    # find executable, determine version
    if opts and opts.exe:
        exepath = find_exe("python", opts.exe)
        code = "import sys; print '.'.join(str(x) for x in sys.version_info)"
        version = extract_version(exepath, ["-c", code])
    else:
        exepath = sys.executable
        strver = '.'.join(str(x) for x in sys.version_info[:3])
        version = Version(strver)

    check_version(version, version_range)

    with make_py_package("python", version, path) as pkg:
        pkg.add_variant(*system.variant)
        pkg.set_tools("python")
        pkg.set_commands(commands)
        pkg.add_link(exepath, root("bin", "python"))

    return ("python", version)
