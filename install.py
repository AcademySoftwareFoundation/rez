"""
This script uses venv/virtualenv to create a standalone, production-ready Rez
installation in the specified directory.
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

# Note: The following imports are carefully selected, they will work even
# though rez is not yet built.
#
from rez.utils._version import _rez_version  # noqa: E402
from rez.cli._entry_points import get_specifications  # noqa: E402
from rez.backport.shutilwhich import which  # noqa: E402
from rez.vendor.distlib.scripts import ScriptMaker  # noqa: E402

# switch to builtin venv in python 3.7+
#
# Note: There are issues using venv with 3.6. Installed pip version is 18.2
# (which isn't high enough for rez-pip to behave correctly). 3.7 installs pip
# version 20.1.
#
use_venv = (sys.version_info[:2] >= (3, 7))

if use_venv:
    import venv
else:
    from build_utils.virtualenv.virtualenv import create_environment, path_locations


def create_virtual_environment(dest_dir):
    if use_venv:
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(dest_dir)
    else:
        create_environment(dest_dir)


def get_virtualenv_bin_dir(dest_dir):
    if use_venv:
        builder = venv.EnvBuilder()
        context = builder.ensure_directories(dest_dir)
        return context.bin_path
    else:
        _, _, _, bin_dir = path_locations(dest_dir)
        return bin_dir


def get_virtualenv_py_executable(dest_dir):
    # get virtualenv's python executable
    bin_dir = get_virtualenv_bin_dir(dest_dir)

    env = {
        "PATH": bin_dir,
        "PATHEXT": os.environ.get("PATHEXT", "")
    }

    return bin_dir, which("python", env=env)


def run_command(args, cwd=source_path):
    if opts.verbose:
        print("running in %s: %s" % (cwd, " ".join(args)))
    return subprocess.check_output(args, cwd=source_path)


def patch_rez_binaries(dest_dir):
    virtualenv_bin_path, py_executable = get_virtualenv_py_executable(dest_dir)

    specs = get_specifications()

    # delete rez bin files written into virtualenv
    for name in specs.keys():
        filepath = os.path.join(virtualenv_bin_path, name)
        if os.path.isfile(filepath):
            os.remove(filepath)

    # write patched bins instead. These go into 'bin/rez' subdirectory, which
    # gives us a bin dir containing only rez binaries. This is what we want -
    # we don't want resolved envs accidentally getting the virtualenv's 'python'.
    dest_bin_path = os.path.join(virtualenv_bin_path, "rez")
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
    for root, _, _ in os.walk(path):
        if root.endswith(os.path.sep + "rez" + os.path.sep + "completion"):
            completion_path = root
            break

    # copy completion scripts into root of virtualenv for ease of use
    if completion_path:
        dest_path = os.path.join(dest_dir, "completion")
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)
        shutil.copytree(completion_path, dest_path)
        return dest_path

    return None


def install(dest_dir, print_welcome=False):
    """Install rez into the given directory.

    Args:
        dest_dir (str): Full path to the install directory.
    """
    print("installing rez to %s..." % dest_dir)

    # create the virtualenv
    create_virtual_environment(dest_dir)

    # install rez from source
    install_rez_from_source(dest_dir)

    # patch the rez binaries
    patch_rez_binaries(dest_dir)

    # copy completion scripts into virtualenv
    completion_path = copy_completion_scripts(dest_dir)

    # mark virtualenv as production rez install. Do not remove - rez uses this!
    virtualenv_bin_dir = get_virtualenv_bin_dir(dest_dir)
    dest_bin_dir = os.path.join(virtualenv_bin_dir, "rez")
    validation_file = os.path.join(dest_bin_dir, ".rez_production_install")
    with open(validation_file, 'w') as f:
        f.write(_rez_version)

    # done
    if print_welcome:
        print()
        print("SUCCESS!")
        rez_exe = os.path.realpath(os.path.join(dest_bin_dir, "rez"))
        print("Rez executable installed to: %s" % rez_exe)

        try:
            out = subprocess.check_output([
                rez_exe,
                "python",
                "-c",
                "import rez; print(rez.__path__[0])"
            ])
            pkg_path = os.path.realpath(out.strip())
            print("Rez python package installed to: %s" % pkg_path)
        except:
            pass  # just in case there's an issue with rez-python tool

        print()
        print("To activate Rez, add the following path to $PATH:")
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


def install_rez_from_source(dest_dir):
    _, py_executable = get_virtualenv_py_executable(dest_dir)

    # install via pip
    run_command([py_executable, "-m", "pip", "install", "."])


def install_as_rez_package(repo_path):
    """Installs rez as a rez package.

    Note that this can be used to install new variants of rez into an existing
    rez package (you may require multiple platform installations for example).

    Args:
        repo_path (str): Full path to the package repository to install into.
    """
    from tempfile import mkdtemp

    # do a temp production (virtualenv-based) rez install
    tmpdir = mkdtemp(prefix="rez-install-")
    install(tmpdir)
    _, py_executable = get_virtualenv_py_executable(tmpdir)

    try:
        # This extracts a rez package from the installation. See
        # rez.utils.installer.install_as_rez_package for more details.
        #
        args = (
            py_executable, "-E", "-c",
            r"from rez.utils.installer import install_as_rez_package;"
            r"install_as_rez_package(%r)" % repo_path
        )
        print(subprocess.check_output(args))

    finally:
        # cleanup temp install
        try:
            shutil.rmtree(tmpdir)
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "Rez installer", description="Install rez in a production ready, "
                                     "standalone Python virtual environment.")
    parser.add_argument(
        '-v', '--verbose', action='count', dest='verbose', default=0,
        help="Increase verbosity.")
    parser.add_argument(
        '-s', '--keep-symlinks', action="store_true", default=False,
        help="Don't run realpath on the passed DIR to resolve symlinks; "
             "ie, the baked script locations may still contain symlinks")
    parser.add_argument(
        '-p', '--as-rez-package', action="store_true",
        help="Install rez as a rez package. Note that this installs the API "
        "only (no cli tools), and DIR is expected to be the path to a rez "
        "package repository (and will default to ~/packages instead).")
    parser.add_argument(
        "DIR", nargs='?',
        help="Destination directory. If '{version}' is present, it will be "
        "expanded to the rez version. Default: /opt/rez")

    opts = parser.parse_args()

    if " " in os.path.realpath(__file__):
        parser.error(
            "\nThe absolute path of install.py cannot contain spaces due to setuptools limitation.\n"
            "Please move installation files to another location or rename offending folder(s).\n"
        )

    # determine install path
    if opts.DIR:
        path = opts.DIR
    elif opts.as_rez_package:
        path = "~/packages"
    else:
        path = "/opt/rez"

    if opts.as_rez_package:
        dest_dir = path
    else:
        dest_dir = path.format(version=_rez_version)

    dest_dir = os.path.expanduser(dest_dir)
    if not opts.keep_symlinks:
        dest_dir = os.path.realpath(dest_dir)

    # perform the installation
    if opts.as_rez_package:
        install_as_rez_package(dest_dir)
    else:
        install(dest_dir, print_welcome=True)
