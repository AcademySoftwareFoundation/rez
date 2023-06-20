# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Creates the 'hello_world' testing package.

Note: Even though this is a python-based package, it does not list python as a
requirement. This is not typical! This package is intended as a very simple test
case, and for that reason we do not want any dependencies.
"""
from __future__ import absolute_import, print_function

from rez.package_maker import make_package
from rez.vendor.version.version import Version
from rez.utils.lint_helper import env
from rez.utils.execution import create_executable_script, ExecutableScriptMode
from rez.bind._utils import make_dirs, check_version
import os.path


def setup_parser(parser):
    parser.add_argument(
        "--py-script-mode", type=str, default="platform_specific", metavar="PY_SCRIPT_MODE",
        help="py script mode to use (default: %(default)s).",
        choices=(ExecutableScriptMode._member_names_),
    )


def commands():
    env.PATH.append('{this.root}/bin')
    env.OH_HAI_WORLD = "hello"


def hello_world_source():
    import sys
    from optparse import OptionParser

    p = OptionParser()
    p.add_option("-q", dest="quiet", action="store_true",
                 help="quiet mode")
    p.add_option("-r", dest="retcode", type="int", default=0,
                 help="exit with a non-zero return code")
    opts, args = p.parse_args()

    if not opts.quiet:
        print("Hello Rez World!")
    sys.exit(opts.retcode)


def bind(path, version_range=None, py_script_mode=None, opts=None, parser=None):
    version = Version("1.0")
    check_version(version, version_range)

    # Allow the user to override the `py_script_mode` via the command line
    # or via python API, as is the case for unit tests. Fall back to
    # `platform_specific` if not specified.
    py_script_mode = opts.py_script_mode if opts else py_script_mode
    if py_script_mode is None:
        py_script_mode = ExecutableScriptMode.platform_specific
    else:
        # Extra error checking for the python API
        if py_script_mode not in ExecutableScriptMode._member_names_:
            raise ValueError(
                "Invalid py_script_mode: {!r} Choose between: {!r}".format(
                    py_script_mode, ExecutableScriptMode._member_names_
                )
            )
        py_script_mode = ExecutableScriptMode[py_script_mode]

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")
        filepath = os.path.join(binpath, "hello_world")

        create_executable_script(
            filepath,
            hello_world_source,
            py_script_mode=py_script_mode,
        )

    with make_package("hello_world", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["hello_world"]
        pkg.commands = commands

    return pkg.installed_variants
