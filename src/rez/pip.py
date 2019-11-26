from __future__ import print_function, absolute_import

from rez.packages_ import get_latest_package
from rez.vendor.version.version import Version, VersionError
from rez.vendor.distlib import DistlibException
from rez.vendor.distlib.database import DistributionPath
from rez.vendor.distlib.markers import interpret
from rez.vendor.distlib.util import parse_name_and_version
from rez.vendor.enum.enum import Enum
from rez.vendor.six.six import StringIO
from rez.resolved_context import ResolvedContext
from rez.utils.execution import Popen
from rez.utils.pip import get_rez_requirements, pip_to_rez_package_name, \
    pip_to_rez_version
from rez.utils.logging_ import print_debug, print_info, print_warning
from rez.exceptions import BuildError, PackageFamilyNotFoundError, \
    PackageNotFoundError, RezSystemError, convert_errors
from rez.package_maker__ import make_package
from rez.config import config
from rez.system import System
from rez.utils.platform_ import platform_

from tempfile import mkdtemp
from pipes import quote
from pprint import pformat
import subprocess
import os.path
import shutil
import sys
import os


class InstallMode(Enum):
    # don't install dependencies. Build may fail, for example the package may
    # need to compile against a dependency. Will work for pure python though.
    no_deps = 0
    # only install dependencies that we have to. If an existing rez package
    # satisfies a dependency already, it will be used instead. The default.
    min_deps = 1


def is_exe(fpath):
    return os.path.exists(fpath) and os.access(fpath, os.X_OK)


def run_pip_command(command_args, pip_version=None, python_version=None):
    """Run a pip command.
    Args:
        command_args (list of str): Args to pip.
    Returns:
        `subprocess.Popen`: Pip process.
    """
    py_exe, context = find_pip(pip_version, python_version)
    command = [py_exe, "-m", "pip"] + list(command_args)

    if context is None:
        return Popen(command)
    else:
        return context.execute_shell(command=command, block=False)


def find_pip(pip_version=None, python_version=None):
    """Find pip.

    Pip is searched in the following order:

        1. Search for rezified python matching python version request;
        2. If found, test if pip is present;
        3. If pip is present, use it;
        4. If not present, search for rezified pip (this is for backwards compatibility);
        5. If rezified pip is found, use it;
        6. If not, fall back to rez's python installation.

    Args:
        pip_version (str or `Version`): Version of pip to use, or latest if None.
        python_version (str or `Version`): Python version to use, or latest if
            None.

    Returns:
        2-tuple:
        - str: Python executable.
        - `ResolvedContext`: Context containing pip, or None if we fell back
          to system pip.
    """
    py_exe = None
    context = None

    py_exe, pip_version, context = find_pip_from_context(
        python_version,
        pip_version=pip_version
    )

    if not py_exe:
        py_exe, pip_version, context = find_pip_from_context(
            python_version,
            pip_version=pip_version or "latest"
        )

    if not py_exe:
        import pip
        pip_version = pip.__version__
        py_exe = sys.executable
        print_warning(
            "Found no pip in python and pip package; "
            "falling back to pip installed in rez own virtualenv (version %s)",
            pip_version
        )

    pip_major = pip_version.split('.')[0]
    if int(pip_major) < 19:
        raise RezSystemError("pip >= 19 is required! Please update your pip.")

    return py_exe, context


def find_pip_from_context(python_version, pip_version=None):
    """Find pip from rez context.

    Args:
        python_version (str or `Version`): Python version to use
        pip_version (str or `Version`): Version of pip to use, or latest.

    Returns:
        3-tuple:
        - str: Python executable or None if we fell back to system pip.
        - str: Pip version or None if we fell back to system pip.
        - `ResolvedContext`: Context containing pip, or None if we fell back
          to system pip.
    """
    target = "python"
    package_request = []

    if python_version:
        ver = Version(str(python_version))
        python_major_minor_ver = ver.trim(2)
    else:
        # use latest major.minor
        package = get_latest_package("python")
        if package:
            python_major_minor_ver = package.version.trim(2)
        else:
            raise BuildError("Found no python package.")

    python_package = "python-%s" % str(python_major_minor_ver)

    package_request.append(python_package)

    if pip_version:
        target = "pip"
        if pip_version == "latest":
            package_request.append("pip")
        else:
            package_request.append("pip-%s" % str(pip_version))

    print_info("Trying to use pip from %s package", target)

    try:
        context = ResolvedContext(package_request)
    except (PackageFamilyNotFoundError, PackageNotFoundError):
        print_debug("No rez package called %s found", target)
        return None, None, None

    py_exe_name = "python"
    if platform_.name != "windows":
        # Python < 2 on Windows doesn't have versionned executable.
        py_exe_name += str(python_major_minor_ver.trim(1))

    py_exe = context.which(py_exe_name)

    proc = context.execute_command(
        # -E and -s are used to isolate the environment as much as possible.
        # See python --help for more details. We absolutely don't want to get
        # pip from the user home.
        [py_exe, "-E", "-s", "-c", "import pip, sys; sys.stdout.write(pip.__version__)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate()
    if proc.returncode:
        print_debug("Failed to get pip from package %s", target)
        print_debug(out)
        print_debug(err)
        return None, None, None

    pip_version = out.strip()

    variant = context.get_resolved_package(target)
    package = variant.parent
    print_info(
        "Found pip-%s inside %s. Will use it with %s",
        pip_version,
        package.uri,
        py_exe
    )

    return py_exe, pip_version, context


def pip_install_package(source_name, pip_version=None, python_version=None,
                        mode=InstallMode.min_deps, release=False, prefix=None):
    """Install a pip-compatible python package as a rez package.
    Args:
        source_name (str): Name of package or archive/url containing the pip
            package source. This is the same as the arg you would pass to
            the 'pip install' command.
        pip_version (str or `Version`): Version of pip to use to perform the
            install, uses latest if None.
        python_version (str or `Version`): Python version to use to perform the
            install, and subsequently have the resulting rez package depend on.
        mode (`InstallMode`): Installation mode, determines how dependencies are
            managed.
        release (bool): If True, install as a released package; otherwise, it
            will be installed as a local package.

    Returns:
        2-tuple:
            List of `Variant`: Installed variants;
            List of `Variant`: Skipped variants (already installed).
    """
    installed_variants = []
    skipped_variants = []

    py_exe, context = find_pip(pip_version, python_version)
    print_info(
        "Installing %r with pip taken from %r",
        source_name, py_exe
    )

    # TODO: should check if packages_path is writable before continuing with pip
    #
    if prefix is not None:
        packages_path = prefix
    else:
        packages_path = (config.release_packages_path if release
                         else config.local_packages_path)

    tmpdir = mkdtemp(suffix="-rez", prefix="pip-")
    stagingdir = os.path.join(tmpdir, "rez_staging")
    stagingsep = "".join([os.path.sep, "rez_staging", os.path.sep])

    destpath = os.path.join(stagingdir, "python")
    # TODO use binpath once https://github.com/pypa/pip/pull/3934 is approved
    binpath = os.path.join(stagingdir, "bin")

    if context and config.debug("package_release"):
        buf = StringIO()
        print("\n\npackage download environment:", file=buf)
        context.print_info(buf)
        _log(buf.getvalue())

    # Build pip commandline
    cmd = [
        py_exe, "-m", "pip", "install",
        "--use-pep517",
        "--target=%s" % destpath
    ]

    if mode == InstallMode.no_deps:
        cmd.append("--no-deps")
    cmd.append(source_name)

    _cmd(context=context, command=cmd)
    _system = System()

    # determine version of python in use
    if context is None:
        # since we had to use system pip, we have to assume system python version
        py_ver_str = '.'.join(map(str, sys.version_info))
        py_ver = Version(py_ver_str)
    else:
        python_variant = context.get_resolved_package("python")
        py_ver = python_variant.version

    # moving bin folder to expected relative location as per wheel RECORD files
    staged_binpath = os.path.join(destpath, "bin")
    if os.path.isdir(staged_binpath):
        shutil.move(os.path.join(destpath, "bin"), binpath)

    # Collect resulting python packages using distlib
    distribution_path = DistributionPath([destpath])
    distributions = list(distribution_path.get_distributions())
    dist_names = [x.name for x in distributions]

    # get list of package and dependencies
    for distribution in distributions:
        # convert pip requirements into rez requirements
        rez_requires = get_rez_requirements(
            installed_dist=distribution,
            python_version=py_ver,
            name_casings=dist_names
        )

        # log the pip -> rez translation, for debugging
        _log(
            "Pip to rez translation information for " +
            distribution.name_and_version +
            ":\n" +
            pformat({
                "pip": {
                    "run_requires": map(str, distribution.run_requires)
                },
                "rez": rez_requires
            }
        ))

        # iterate over installed files and determine dest filepaths
        tools = []
        src_dst_lut = {}

        for installed_file in distribution.list_installed_files():
            # distlib expects the script files to be located in ../../bin/
            # when in fact ../bin seems to be the resulting path after the
            # installation as such we need to point the bin files to the
            # expected location to match wheel RECORD files
            installed_filepath = os.path.normpath(installed_file[0])
            bin_prefix = os.path.join('..', '..', 'bin') + os.sep

            if installed_filepath.startswith(bin_prefix):
                # account for extra parentdir as explained above
                installed = os.path.join(destpath, '_', installed_filepath)
            else:
                installed = os.path.join(destpath, installed_filepath)

            source_file = os.path.normpath(installed)

            if os.path.exists(source_file):
                destination_file = os.path.relpath(source_file, stagingdir)
                exe = False

                if is_exe(source_file) and destination_file.startswith("bin" + os.sep):
                    _file = os.path.basename(destination_file)
                    tools.append(_file)
                    exe = True

                src_dst_lut[source_file] = [destination_file, exe]
            else:
                _log("Source file does not exist: " + source_file + "!")

        def make_root(variant, path):
            """Using distlib to iterate over all installed files of the current
            distribution to copy files to the target directory of the rez package
            variant
            """
            for source_file, data in src_dst_lut.items():
                destination_file, exe = data
                destination_file = os.path.normpath(os.path.join(path, destination_file))

                if not os.path.exists(os.path.dirname(destination_file)):
                    os.makedirs(os.path.dirname(destination_file))

                shutil.copyfile(source_file, destination_file)
                if exe:
                    shutil.copystat(source_file, destination_file)

        # create the rez package
        name = pip_to_rez_package_name(distribution.name)
        version = pip_to_rez_version(distribution.version)
        requires = rez_requires["requires"]
        variant_requires = rez_requires["variant_requires"]
        metadata = rez_requires["metadata"]

        with make_package(name, packages_path, make_root=make_root) as pkg:
            # basics (version etc)
            pkg.version = version

            if distribution.metadata.summary:
                pkg.description = distribution.metadata.summary

            # requirements and variants
            if requires:
                pkg.requires = requires

            if variant_requires:
                pkg.variants = [variant_requires]

            # commands
            commands = []
            commands.append("env.PYTHONPATH.append('{root}/python')")

            if tools:
                pkg.tools = tools
                commands.append("env.PATH.append('{root}/bin')")

            pkg.commands = '\n'.join(commands)

            # Make the package use hashed variants. This is required because we
            # can't control what ends up in its variants, and that can easily
            # include problematic chars (>, +, ! etc).
            # TODO: https://github.com/nerdvegas/rez/issues/672
            #
            pkg.hashed_variants = True

            # add some custom attributes to retain pip-related info
            pkg.pip_name = distribution.name_and_version
            pkg.from_pip = True
            pkg.is_pure_python = metadata["is_pure_python"]

        installed_variants.extend(pkg.installed_variants or [])
        skipped_variants.extend(pkg.skipped_variants or [])

    # cleanup
    shutil.rmtree(tmpdir)

    return installed_variants, skipped_variants


def _cmd(context, command):
    cmd_str = ' '.join(quote(x) for x in command)
    _log("running: %s" % cmd_str)

    if context is None:
        p = Popen(command)
    else:
        p = context.execute_shell(command=command, block=False)

    with p:
        p.wait()

    if p.returncode:
        raise BuildError("Failed to download source with pip: %s" % cmd_str)


_verbose = config.debug("package_release")


def _log(msg):
    if _verbose:
        print_debug(msg)


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
