"""
Binds a python executable as a rez package.
"""
from __future__ import absolute_import

import os
import sys

from rez.bind._utils import check_version, find_exe, extract_version, make_dirs
from rez.package_maker__ import make_package
from rez.system import system
from rez.utils.lint_helper import env
from rez.utils.platform_ import platform_
from rez.vendor.version.version import Version


def setup_parser(parser):
    parser.add_argument("--exe", type=str, metavar="PATH",
                        help="bind an interpreter other than the current "
                        "python interpreter")


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

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")
        link = os.path.join(binpath, "python")
        platform_.symlink(exepath, link)

    with make_package("python", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["python"]
        pkg.commands = commands
        pkg.variants = [system.variant]

    return "python", version
