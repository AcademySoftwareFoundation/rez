from __future__ import print_function, absolute_import

from rez.packages_ import get_latest_package
from rez.vendor.version.version import Version, VersionError
from rez.vendor.distlib import DistlibException
from rez.vendor.distlib.database import DistributionPath
from rez.vendor.distlib.markers import interpret
from rez.vendor.distlib.util import parse_name_and_version
from rez.vendor.enum.enum import Enum
from rez.resolved_context import ResolvedContext
from rez.utils.system import popen
from rez.utils.pip import get_rez_requirements, pip_to_rez_package_name, \
    pip_to_rez_version
from rez.utils.logging_ import print_debug, print_info, print_warning
from rez.exceptions import BuildError, PackageFamilyNotFoundError, \
    PackageNotFoundError, RezSystemError, convert_errors
from rez.package_maker__ import make_package
from rez.config import config
from rez.system import System

from tempfile import mkdtemp
from StringIO import StringIO
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
    # install dependencies even if an existing rez package satisfies the
    # dependency, if the dependency is newer.
    new_deps = 2
    # install dependencies even if a rez package of the same version is already
    # available, if possible. For example, if you are performing a local install,
    # a released (central) package may match a dependency; but with this mode
    # enabled, a new local package of the same version will be installed as well.
    #
    # Typically, if performing a central install with the rez-pip --release flag,
    # max_deps is equivalent to new_deps.
    max_deps = 3


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
        return popen(command)
    else:
        return context.execute_shell(command=command, block=False)


def find_pip(pip_version=None, python_version=None):
    """Find pip.

    Will revert to native pip installed with rez, if a pip rez package cannot
    be found. In this case, None is returned.

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
    py_exe = "python"
    context = None

    # find pip, fall back to system if rez pip package not found
    try:
        context = create_context(pip_version, python_version)
        py_exe = context.which("python")
    except BuildError:
        # fall back on system pip
        py_exe = sys.executable
        print_info("Using %s -m pip", py_exe)

    # check version, must be >=19
    if context:
        proc = context.execute_command(
            [py_exe, "-c", "import pip; print pip.__version__"],
            stdout=subprocess.PIPE
        )
        out, _ = proc.communicate()
        pip_version = out.strip()

    else:
        import pip
        pip_version = pip.__version__

    pip_major = pip_version.split('.')[0]
    if int(pip_major) < 19:
        raise RezSystemError("pip >= 19 is required! Please update your pip.")

    return py_exe, context


def create_context(pip_version=None, python_version=None):
    """Create a context containing the specific pip and python.

    Args:
        pip_version (str or `Version`): Version of pip to use, or latest if None.
        python_version (str or `Version`): Python version to use, or latest if
            None.

    Returns:
        `ResolvedContext`: Context containing pip and python.
    """
    # determine pip pkg to use for install, and python variants to install on
    if pip_version:
        pip_req = "pip-%s" % str(pip_version)
    else:
        pip_req = "pip"

    if python_version:
        ver = Version(str(python_version))
        major_minor_ver = ver.trim(2)
        py_req = "python-%s" % str(major_minor_ver)
    else:
        # use latest major.minor
        package = get_latest_package("python")
        if package:
            major_minor_ver = package.version.trim(2)
        else:
            # no python package. We're gonna fail, let's just choose current
            # python version (and fail at context creation time)
            major_minor_ver = '.'.join(map(str, sys.version_info[:2]))

        py_req = "python-%s" % str(major_minor_ver)

    # use pip + latest python to perform pip download operations
    request = [pip_req, py_req]

    with convert_errors(from_=(PackageFamilyNotFoundError, PackageNotFoundError),
                        to=BuildError, msg="Cannot run - pip or python rez "
                        "package is not present"):
        context = ResolvedContext(request)

    # print pip package used to perform the install
    pip_variant = context.get_resolved_package("pip")
    pip_package = pip_variant.parent
    print_info("Using %s (%s)" % (pip_package.qualified_name, pip_variant.uri))

    return context


def pip_install_package(source_name, pip_version=None, python_version=None,
                        mode=InstallMode.min_deps, release=False):
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

    # TODO: should check if packages_path is writable before continuing with pip
    #
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
        p = popen(command)
    else:
        p = context.execute_shell(command=command, block=False)

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
