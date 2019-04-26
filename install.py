"""
This script uses an embedded copy of virtualenv to create a standalone,
production-ready Rez installation in the specified directory.
"""
import os
import sys
import shutil
import os.path
import subprocess
from optparse import OptionParser

source_path = os.path.dirname(os.path.realpath(__file__))
bin_path = os.path.join(source_path, "bin")
src_path = os.path.join(source_path, "src")
sys.path.insert(0, src_path)

from rez.utils._version import _rez_version
from rez.backport.shutilwhich import which
from build_utils.virtualenv.virtualenv import (
    Logger,
    create_environment,
    path_locations
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


if __name__ == "__main__":
    usage = ("usage: %prog [options] DEST_DIR ('{version}' in DEST_DIR will "
             "expand to Rez version)")
    parser = OptionParser(usage=usage)
    parser.add_option(
        '-v', '--verbose', action='count', dest='verbose', default=0,
        help="Increase verbosity.")
    parser.add_option(
        '-s', '--keep-symlinks', action="store_true", default=False,
        help="Don't run realpath on the passed DEST_DIR to resolve symlinks; "
             "ie, the baked script locations may still contain symlinks")
    opts, args = parser.parse_args()

    if " " in os.path.realpath(__file__):
        parser.error(
            "\nThe absolute path of install.py cannot contain "
            "spaces due to setuptools limitation.\n"
            "Please move installation files to another "
            "location or rename offending folder(s).\n"
        )

    # determine install path
    if len(args) != 1:
        parser.error("expected DEST_DIR")

    dest_dir = args[0].format(version=_rez_version)
    dest_dir = os.path.expanduser(dest_dir)
    if not opts.keep_symlinks:
        dest_dir = os.path.realpath(dest_dir)

    print "installing rez to %s..." % dest_dir

    # make virtualenv verbose
    log_level = Logger.level_for_integer(2 - opts.verbose)
    logger = Logger([(log_level, sys.stdout)])

    # create the virtualenv
    create_environment(dest_dir)

    # install rez from source
    _, _, _, venv_bin_dir = path_locations(dest_dir)
    py_executable = which("python", env={
        "PATH": venv_bin_dir,
        "PATHEXT": os.environ.get("PATHEXT", "")
    })
    args = [py_executable, "setup.py", "install"]
    if opts.verbose:
        print "running in %s: %s" % (source_path, " ".join(args))
    p = subprocess.Popen(args, cwd=source_path)
    p.wait()

    # copy completion scripts into venv
    completion_path = copy_completion_scripts(dest_dir)

    # mark venv as production rez install. Do not remove - rez uses this!
    dest_bin_dir = os.path.join(venv_bin_dir, "rez")
    validation_file = os.path.join(dest_bin_dir, ".rez_production_install")
    with open(validation_file, 'w') as f:
        f.write(_rez_version)

    # done
    print
    print "SUCCESS! To activate Rez, add the following path to $PATH:"
    print dest_bin_dir

    if completion_path:
        print('')
        shell = os.getenv('SHELL')

        if shell:
            shell = os.path.basename(shell)
            ext = "csh" if "csh" in shell else "sh"  # Basic selection logic

            print("You may also want to source the "
                  "completion script (for %s):" % shell)
            print("source {0}/complete.{1}".format(completion_path, ext))
        else:
            print("You may also want to source the "
                  "relevant completion script from:")
            print(completion_path)

    print('')
