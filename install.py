"""
This script uses an embedded copy of virtualenv to create a standalone,
production-ready Rez installation in the specified directory.
"""
import os
import sys
import shutil
import os.path
import textwrap
import subprocess
from optparse import OptionParser

source_path = os.path.dirname(__file__)
bin_path = os.path.join(source_path, "bin")
src_path = os.path.join(source_path, "src")
sys.path.insert(0, src_path)

from rez._version import _rez_version
from build_utils.virtualenv.virtualenv import make_exe, Logger, logger, \
    create_environment
from build_utils.distlib.scripts import ScriptMaker


class fake_entry(object):
    code_template = textwrap.dedent(
        """
        # EASY-INSTALL-SCRIPT: 'rez=={rez_version}','{name}'
        __requires__ = 'rez=={rez_version}'
        import pkg_resources
        pkg_resources.run_script('rez=={rez_version}', '{name}')
        """)

    def __init__(self, name):
        self.name = name

    def get_script_text(self):
        return self.code_template.format(rez_version=_rez_version,
                                         name=self.name)


class _ScriptMaker(ScriptMaker):
    def __init__(self, *nargs, **kwargs):
        super(_ScriptMaker, self).__init__(*nargs, **kwargs)
        self.variants = set(('',))

    def _get_script_text(self, entry):
        return entry.get_script_text()


def patch_rez_binaries(dest_dir):
    bin_names = os.listdir(bin_path)
    dest_bin_path = os.path.join(dest_dir, "bin")
    venv_py_executable = os.path.join(dest_bin_path, "python")
    assert os.path.exists(venv_py_executable)

    maker = _ScriptMaker(bin_path, dest_bin_path)
    maker.executable = venv_py_executable
    options = dict(interpreter_args=["-E"])

    for name in bin_names:
        # delete bin file written by setuptools
        filepath = os.path.join(dest_bin_path, name)
        if os.path.exists(filepath):
            os.remove(filepath)

        # write patched bin instead
        entry = fake_entry(name)
        maker._make_script(entry, [], options=options)


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
        shutil.copytree(completion_path, dest_path)
        return dest_path

    return None


if __name__ == "__main__":
    usage = "usage: %prog [options] DEST_DIR"
    parser = OptionParser(usage=usage)
    parser.add_option(
        '-s', '--subdir', action='store_true',
        help="Add a subdirectory named 'rez-<VERSION>' to the install path")
    parser.add_option(
        '-v', '--verbose', action='count', dest='verbose', default=0,
        help="Increase verbosity.")
    opts, args = parser.parse_args()

    # determine install path
    if len(args) != 1:
        parser.error("expected DEST_DIR")
    dest_dir = os.path.expanduser(args[0])
    dest_dir = os.path.realpath(dest_dir)

    if opts.subdir:
        dir_ = "rez-%s" % _rez_version
        dest_dir = os.path.join(dest_dir, dir_)

        # pretty safe to delete this dir if it already exists...
        if os.path.exists(dest_dir):
            print "removing previous rez install from %s..." % dest_dir
            shutil.rmtree(dest_dir)

    print "installing rez to %s..." % dest_dir

    # make virtualenv verbose
    log_level = Logger.level_for_integer(2 - opts.verbose)
    logger = Logger([(log_level, sys.stdout)])

    # create the virtualenv
    create_environment(dest_dir)

    # install rez from source
    py_executable = os.path.join(dest_dir, "bin", "python")
    args = [py_executable, "setup.py", "install"]
    p = subprocess.Popen(args, cwd=source_path)
    p.wait()

    # patch the rez binaries
    patch_rez_binaries(dest_dir)

    # copy completion scripts into venv
    completion_path = copy_completion_scripts(dest_dir)

    # mark venv as production rez install. Do not remove - rez uses this!
    validation_file = os.path.join(dest_dir, "rez_production_install")
    with open(validation_file, 'w') as f:
        pass

    # done
    print
    print "SUCCESS! To activate Rez, add the following path to $PATH:"
    print os.path.join(dest_dir, "bin")

    if completion_path:
        print "You may also want to source the relevant completion script from:"
        print completion_path
    print
