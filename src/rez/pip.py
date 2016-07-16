from rez.packages_ import get_latest_package
from rez.vendor.version.version import Version
from rez.vendor.distlib import DistlibException
from rez.vendor.distlib.database import DistributionPath
from rez.vendor.distlib.markers import interpret
from rez.vendor.distlib.util import parse_name_and_version
from rez.vendor.enum.enum import Enum
from rez.resolved_context import ResolvedContext
from rez.utils.logging_ import print_debug
from rez.exceptions import BuildError, PackageFamilyNotFoundError, \
    PackageNotFoundError, convert_errors
from rez.package_maker__ import make_package
from rez.config import config
from rez.system import System
from tempfile import mkdtemp
from StringIO import StringIO
from pipes import quote
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


def _get_dependencies(requirement, distributions):
    def get_distrubution_name(pip_name):
        pip_to_rez_name = pip_name.lower().replace("-", "_")
        for dist in distributions:
            _name, _ = parse_name_and_version(dist.name_and_version)
            if _name.replace("-", "_") == pip_to_rez_name:
                return dist.name.replace("-", "_")

    result = []
    requirements = ([requirement] if isinstance(requirement, basestring)
                    else requirement["requires"])

    for package in requirements:
        if "(" in package:
            try:
                name, version = parse_name_and_version(package)
                version = version.replace("==", "")
                name = get_distrubution_name(name)
            except DistlibException:
                n, vs = package.split(' (')
                vs = vs[:-1]
                versions = []
                for v in vs.split(','):
                    package = "%s (%s)" % (n, v)
                    name, version = parse_name_and_version(package)
                    version = version.replace("==", "")
                    versions.append(version)
                version = "".join(versions)

            name = get_distrubution_name(name)
            result.append("-".join([name, version]))
        else:
            name = get_distrubution_name(package)
            result.append(name)

    return result


def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)


def pip_install_package(source_name, pip_version=None, python_versions=None,
                        mode=InstallMode.min_deps, release=False):
    """Install a pip-compatible python package as a rez package.
    Args:
        source_name (str): Name of package or archive/url containing the pip
            package source. This is the same as the arg you would pass to
            the 'pip install' command.
        pip_version (str or `Version`): Version of pip to use to perform the
            install, uses latest if None.
        python_versions (list of str or `Version`): Python version(s) to use to
            perform the install, and subsequently have the resulting rez package
            depend on. If multiple values are provided, this will create
            multiple variants in the package, each based on the python version.
            Defaults to a single variant for the latest python version.
        mode (`InstallMode`): Installation mode, determines how dependencies are
            managed.

    Returns:
        2-tuple:
            List of `Variant`: Installed variants;
            List of `Variant`: Skipped variants (already installed).
    """
    installed_variants = []
    skipped_variants = []

    # determine pip pkg to use for install, and python variants to install on
    if pip_version:
        pip_req = "pip-%s" % str(pip_version)
    else:
        pip_req = "pip"

    py_reqs = []
    if python_versions:
        py_vers = set()
        for ver in python_versions:
            ver_ = Version(str(ver))
            major_minor_ver = ver_[:2]
            py_vers.add(major_minor_ver)

        for py_ver in sorted(py_vers):
            py_req = "python-%s" % str(py_ver)
            py_reqs.append(py_req)
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
        py_reqs.append(py_req)

    _log("installing for pip: '%s', python(s): %s" % (pip_req, py_reqs))


    # TODO: should check if packages_path is writable before continuing with pip
    #
    packages_path = config.release_packages_path if release else config.local_packages_path


    tmpdir = mkdtemp(suffix="-rez", prefix="pip-")
    stagingdir = os.path.join(tmpdir, "rez_staging")
    destpath = os.path.join(stagingdir, "python")
    binpath = os.path.join(stagingdir, "bin")
    stagingsep = "".join([os.path.sep, "rez_staging", os.path.sep])

    # use pip + latest python to perform pip download operations
    request = [pip_req, py_reqs[-1]]

    with convert_errors(from_=(PackageFamilyNotFoundError, PackageNotFoundError),
                        to=BuildError, msg="Cannot install, pip or python rez "
                        "packages are not present"):
        context = ResolvedContext(request)

    if config.debug("package_release"):
        buf = StringIO()
        print >> buf, "\n\npackage download environment:"
        context.print_info(buf)
        _log(buf.getvalue())

    # Build pip commandline
    cmd = ["pip", "install", "--target", destpath,
           "--install-option=--install-scripts=%s" % binpath]

    if mode == InstallMode.no_deps:
        cmd.append("--no-deps")
    cmd.append(source_name)
    _cmd(context=context, command=cmd)
    _system = System()

    # Collect resulting python packages using distlib
    distribution_path = DistributionPath([destpath], include_egg=True)
    distributions = [d for d in distribution_path.get_distributions()]

    for distribution in distribution_path.get_distributions():
        requirements = []
        if distribution.metadata.run_requires:
            # Handle requirements. Currently handles conditional environment based
            # requirements and normal requirements
            # TODO: Handle optional requirements?
            for requirement in distribution.metadata.run_requires:
                if "environment" in requirement:
                    if interpret(requirement["environment"]):
                        requirements.extend(_get_dependencies(requirement, distributions))
                elif "extra" in requirement:
                    # Currently ignoring optional requirements
                    pass
                else:
                    requirements.extend(_get_dependencies(requirement, distributions))

        tools = []
        src_dst_lut = {}

        for installed_file in distribution.list_installed_files(allow_fail=True):
            source_file = os.path.normpath(os.path.join(destpath, installed_file[0]))
            if os.path.exists(source_file):
                destination_file = installed_file[0].split(stagingsep)[1]
                exe = False

                if is_exe(source_file) and \
                        destination_file.startswith("%s%s" % ("bin", os.path.sep)):
                    _, _file = os.path.split(destination_file)
                    tools.append(_file)
                    exe = True

                data = [destination_file, exe]
                src_dst_lut[source_file] = data
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

        # Inject platform and arch
        if "os-" + _system.os not in py_reqs:
            py_reqs.insert(0, "os-" + _system.os)
        if "arch-" + _system.arch not in py_reqs:
            py_reqs.insert(0, "arch-" + _system.arch)
        if "platform-" + _system.platform not in py_reqs:
            py_reqs.insert(0, "platform-" + _system.platform)


        name, _ = parse_name_and_version(distribution.name_and_version)
        name = distribution.name[0:len(name)].replace("-", "_")

        with make_package(name, packages_path, make_root=make_root) as pkg:
            pkg.version = distribution.version
            if distribution.metadata.summary:
                pkg.description = distribution.metadata.summary

            pkg.variants = [py_reqs]
            if requirements:
                pkg.requires = requirements

            commands = []
            commands.append("env.PYTHONPATH.append('{root}/python')")

            if tools:
                pkg.tools = tools
                commands.append("env.PATH.append('{root}/bin')")

            pkg.commands = '\n'.join(commands)

        installed_variants.extend(pkg.installed_variants or [])
        skipped_variants.extend(pkg.skipped_variants or [])

    # cleanup
    shutil.rmtree(tmpdir)

    return installed_variants, skipped_variants


def _cmd(context, command):
    cmd_str = ' '.join(quote(x) for x in command)
    _log("running: %s" % cmd_str)

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
