"""
This script uses an embedded copy of virtualenv to create a standalone,
production-ready Rez installation in the specified directory.
"""
import sys
import os
import os.path
import subprocess


root_path = os.path.dirname(__file__)
src_path = os.path.join(root_path, "src")
sys.path.insert(0, src_path)


from rez.vendor import argparse
from build_utils.patch_virtualenv import patch_virtualenv
from build_utils.virtualenv import virtualenv


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Rez production installer.')
    parser.add_argument(
        '-v', '--verbose', action='count', dest='verbose', default=0,
        help="Increase verbosity.")
    parser.add_argument(
        "DEST_DIR", type=str,
        help="destination path for rez installation")
    opts = parser.parse_args()

    # make virtualenv verbose
    log_level = virtualenv.Logger.level_for_integer(2 - opts.verbose)
    virtualenv.logger = virtualenv.Logger([(log_level, sys.stdout)])

    # create the virtualenv
    dest_dir = os.path.expanduser(opts.DEST_DIR)
    virtualenv.create_environment(dest_dir)

    # install ourself into the virtualenv
    py_executable = os.path.join(dest_dir, "bin", "python")
    p = subprocess.Popen([py_executable, "setup.py", "install"],
                         cwd=root_path)
    p.wait()

    # patch the virtualenv
    patch_virtualenv(dest_dir)
