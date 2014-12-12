"""
Binds a cmake executable as a rez package.
"""
from __future__ import absolute_import
from rez.package_maker_ import make_py_package, code_provider, root
from rez.bind.utils import check_version, find_exe, extract_version
from rez.system import system
from rez.utils.lint_helper import env


def setup_parser(parser):
    parser.add_argument("--exe", type=str, metavar="PATH",
                        help="manually specify the cmake executable to bind.")


@code_provider
def commands():
    env.PATH.append('{this.root}/bin')


def bind(path, version_range=None, opts=None, parser=None):
    # get path to exe
    exepath = find_exe("cmake", getattr(opts, "exe", None))
    version = extract_version(exepath, "--version")
    check_version(version, version_range)

    with make_py_package("cmake", version, path) as pkg:
        pkg.add_variant(*system.variant)
        pkg.set_tools("cmake")
        pkg.set_commands(commands)
        pkg.add_link(exepath, root("bin", "cmake"))

    return ("cmake", version)
