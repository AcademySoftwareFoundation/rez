"""
This script uses an embedded copy of virtualenv to create a standalone,
production-ready Rez installation in the specified directory.
"""
from __future__ import print_function

import argparse
import os
import sys
import shutil
import os.path
import subprocess


source_path = os.path.dirname(os.path.realpath(__file__))
src_path = os.path.join(source_path, "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version
from rez.cli._entry_points import get_specifications
from rez.backport.shutilwhich import which
from rez.vendor.distlib.scripts import ScriptMaker

from build_utils.virtualenv.virtualenv import create_environment, path_locations


def get_py_venv_executable(dest_dir):
    # get virtualenv's python executable
    _, _, _, venv_bin_dir = path_locations(dest_dir)

    env = {
        "PATH": venv_bin_dir,
        "PATHEXT": os.environ.get("PATHEXT", "")
    }

    return venv_bin_dir, which("python", env=env)


def run_command(args, cwd=source_path):
    if opts.verbose:
        print("running in %s: %s" % (cwd, " ".join(args)))
    return subprocess.check_output(args, cwd=source_path)


def patch_rez_binaries(dest_dir):
    venv_bin_path, py_executable = get_py_venv_executable(dest_dir)

    specs = get_specifications()

    # delete rez bin files written into virtualenv
    for name in specs.keys():
        filepath = os.path.join(venv_bin_path, name)
        if os.path.isfile(filepath):
            os.remove(filepath)

    # write patched bins instead. These go into 'bin/rez' subdirectory, which
    # gives us a bin dir containing only rez binaries. This is what we want -
    # we don't want resolved envs accidentally getting the venv's 'python'.
    dest_bin_path = os.path.join(venv_bin_path, "rez")
    if os.path.exists(dest_bin_path):
        shutil.rmtree(dest_bin_path)
    os.makedirs(dest_bin_path)

    maker = ScriptMaker(
        # note: no filenames are referenced in any specifications, so
        # source_dir is unused
        source_dir=None,
        target_dir=dest_bin_path
    )

    maker.executable = py_executable

    maker.make_multiple(
        specifications=specs.values(),
        # the -E arg is crucial - it means rez cli tools still work within a
        # rez-resolved env, even if PYTHONPATH or related env-vars would have
        # otherwise changed rez's behaviour
        options=dict(interpreter_args=["-E"])
    )


def copy_completion_scripts(dest_dir):
    # find completion dir in rez package
    path = os.path.join(dest_dir, "lib")
    completion_path = None
    for root, dirs, _ in os.walk(path):
        if os.path.basename(root) == "completion":
            completion_path = root
            break

    if completion_path:
        dest_path = os.path.join(dest_dir, "completion")
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)
        shutil.copytree(completion_path, dest_path)
        return dest_path

    return None


def install_rez_from_source(dest_dir):
    _, py_executable = get_py_venv_executable(dest_dir)

    # install via pip
    run_command([py_executable, "-m", "pip", "install", "."])


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Rez installer")
    parser.add_argument(
        '-v', '--verbose', action='count', dest='verbose', default=0,
        help="Increase verbosity.")
    parser.add_argument(
        '-s', '--keep-symlinks', action="store_true", default=False,
        help="Don't run realpath on the passed DEST_DIR to resolve symlinks; "
             "ie, the baked script locations may still contain symlinks")
    parser.add_argument(
        "DIR", default="/opt/rez", nargs='?',
        help="Destination directory. If '{version}' is present, it will be "
        "expanded to the rez version. Default: %(default)s")

    opts = parser.parse_args()

    if " " in os.path.realpath(__file__):
        parser.error(
            "\nThe absolute path of install.py cannot contain spaces due to setuptools limitation.\n"
            "Please move installation files to another location or rename offending folder(s).\n"
        )

    # determine install path
    dest_dir = opts.DIR.format(version=_rez_version)
    dest_dir = os.path.expanduser(dest_dir)
    if not opts.keep_symlinks:
        dest_dir = os.path.realpath(dest_dir)

    print("installing rez to %s..." % dest_dir)

    # create the virtualenv
    create_environment(dest_dir)

    # install rez from source
    install_rez_from_source(dest_dir)

    # patch the rez binaries
    patch_rez_binaries(dest_dir)

    # copy completion scripts into venv
    completion_path = copy_completion_scripts(dest_dir)

    # mark venv as production rez install. Do not remove - rez uses this!
    _, _, _, venv_bin_dir = path_locations(dest_dir)
    dest_bin_dir = os.path.join(venv_bin_dir, "rez")
    validation_file = os.path.join(dest_bin_dir, ".rez_production_install")
    with open(validation_file, 'w') as f:
        f.write(_rez_version)

    # done
    print()
    print("SUCCESS! To activate Rez, add the following path to $PATH:")
    print(dest_bin_dir)

    if completion_path:
        print('')
        shell = os.getenv('SHELL')

        if shell:
            shell = os.path.basename(shell)
            ext = "csh" if "csh" in shell else "sh"  # Basic selection logic

            print("You may also want to source the completion script (for %s):" % shell)
            print("source {0}/complete.{1}".format(completion_path, ext))
        else:
            print("You may also want to source the relevant completion script from:")
            print(completion_path)

    print('')
