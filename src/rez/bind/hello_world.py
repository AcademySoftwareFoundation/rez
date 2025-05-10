# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Creates the 'hello_world' testing package.

Note: Even though this is a python-based package, it does not list python as a
requirement. This is not typical! This package is intended as a very simple test
case, and for that reason we do not want any dependencies.
"""
from rez.package_maker import make_package
from rez.version import Version
from rez.utils.lint_helper import env
from rez.utils.execution import create_executable_script, ExecutableScriptMode
from rez.vendor.distlib.scripts import ScriptMaker
from rez.bind._utils import make_dirs, check_version
import os.path
import shutil


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


def bind(path, version_range=None, opts=None, parser=None):
    version = Version("1.0")
    check_version(version, version_range)

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")
        binpathtmp = make_dirs(root, "bintmp")

        create_executable_script(
            os.path.join(binpathtmp, "hello_world"),
            hello_world_source,
            py_script_mode=ExecutableScriptMode.single,
        )
        create_executable_script(
            os.path.join(binpathtmp, "hello_world_gui"),
            hello_world_source,
            program="pythonw",
            py_script_mode=ExecutableScriptMode.single,
        )

        # We want to use ScriptMaker on all platofrms. This allows us to
        # correctly setup the script to work everywhere, even on Windows.
        # create_executable_script should be fixed to use ScriptMaker
        # instead.
        maker = ScriptMaker(binpathtmp, make_dirs(binpath))
        maker.make("hello_world")
        maker.make("hello_world_gui")
        shutil.rmtree(binpathtmp)

    with make_package("hello_world", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["hello_world", "hello_world_gui"]
        pkg.commands = commands

    return pkg.installed_variants
