from rez.vendor.distlib import DistlibException
from rez.vendor.distlib.database import DistributionPath
from rez.vendor.distlib.markers import interpret
from rez.vendor.distlib.util import parse_name_and_version
from rez.utils.logging_ import print_debug, print_info
from rez.package_maker__ import make_package
from rez.config import config
from rez.utils.platform_ import platform_
from tempfile import mkdtemp

import os
import shutil
import subprocess


def pip_install_package(source_name,
                        release=False,
                        no_deps=False,
                        prefix=None,
                        auto_variants=True,
                        variants=None):
    """Install a pip-compatible python package as a rez package.

    Args:
        source_name (str): Name of package or archive/url containing the pip
            package source. This is the same as the arg you would pass to
            the 'pip install' command.
        prefix (str, optional): Override install location to here,
            similar to `rez build --prefix`
        no_deps (bool, optional): The `pip --no-deps` argument
        auto_variants (bool, optional): Compute variants from the PyPI
            classifiers portion of setup()
        release (bool): If True, install as a released package; otherwise, it
            will be installed as a local package.

    Returns:
        2-tuple:
            List of `Variant`: Installed variants;
            List of `Variant`: Skipped variants (already installed).

    """

    installed_variants = []
    skipped_variants = []

    if prefix is not None:
        config.release_packages_path = prefix
        config.local_packages_path = prefix

    # TODO: should check if packages_path is writable
    # before continuing with pip
    #
    packages_path = (config.release_packages_path if release
                     else config.local_packages_path)

    tmpdir = mkdtemp(suffix="-rez", prefix="pip-")
    stagingdir = os.path.join(tmpdir, "rez_staging")
    stagingsep = "".join([os.path.sep, "rez_staging", os.path.sep])

    destpath = os.path.join(stagingdir, "python")

    # Build pip commandline
    cmd = [
        "python", "-m", "pip", "install",
        "--target", destpath,

        # Only ever consider wheels, anything else is ancient
        "--use-pep517",

        # Handle case where the Python distribution used alongside
        # pip already has a package installed in its `site-packages/` dir.
        "--ignore-installed",
    ]

    if no_deps:
        # Delegate the installation of dependencies to the user
        # This is important, as each dependency may have different
        # requirements of its own, and variants to go with it.
        cmd.append("--no-deps")

    cmd.append(source_name)

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        raise

    # Collect resulting python packages using distlib
    distribution_path = DistributionPath([destpath])
    distributions = [d for d in distribution_path.get_distributions()]

    def pip_to_rez_requirements(distribution):
        """Convert pip-requirements --> rez-requirements"""

        requirements = []
        for req in (distribution.metadata.run_requires or []):
            if "environment" in req:
                if interpret(req["environment"]):
                    requirements += _get_dependencies(req, distributions)

            elif "extra" in req:
                # TODO: Handle optional requirements
                # e.g. requests[security]
                pass

            else:
                requirements += _get_dependencies(req, distributions)

        return requirements

    for distribution in distribution_path.get_distributions():
        src_dst_lut = {}
        files = distribution.list_installed_files()
        requirements = pip_to_rez_requirements(distribution)

        for installed_file in files:
            source_file = os.path.join(destpath, installed_file[0])
            source_file = os.path.normpath(source_file)

            if os.path.exists(source_file):
                destination_file = source_file.split(stagingsep)[1]
                exe = False

                data = [destination_file, exe]
                src_dst_lut[source_file] = data
            else:
                _log("Source file does not exist: " + source_file + "!")

        def make_root(variant, path):
            """Using distlib to iterate over all installed files of the current
            distribution to copy files to the target directory of the rez
            package variant

            """

            for source_file, data in src_dst_lut.items():
                destination_file, exe = data
                destination_file = os.path.join(path, destination_file)
                destination_file = os.path.normpath(destination_file)

                if not os.path.exists(os.path.dirname(destination_file)):
                    os.makedirs(os.path.dirname(destination_file))

                shutil.copyfile(source_file, destination_file)
                if exe:
                    shutil.copystat(source_file, destination_file)

        name, _ = parse_name_and_version(distribution.name_and_version)
        name = distribution.name[0:len(name)].replace("-", "_")

        # determine variant requirements
        variants_ = variants or []

        if (not variants_) and auto_variants:
            wheen_fname = os.path.join(distribution.path, "WHEEL")
            with open(wheen_fname) as f:
                variants_.extend(wheel_to_variants(f.read()))

            if variants_:
                print_info("'%s' - Automatically detected variants: %s" % (
                    name, ", ".join(variants_))
                )

        with make_package(name, packages_path, make_root=make_root) as pkg:
            pkg.version = distribution.version
            if distribution.metadata.summary:
                pkg.description = distribution.metadata.summary

            if variants_:
                pkg.variants = [variants_]

            if requirements:
                pkg.requires = requirements

            pkg.commands = '\n'.join([
                "env.PYTHONPATH.append('{root}/python')"
            ])

        installed_variants.extend(pkg.installed_variants or [])
        skipped_variants.extend(pkg.skipped_variants or [])

    # cleanup
    shutil.rmtree(tmpdir)

    return installed_variants, skipped_variants


def classifiers_to_variants(classifiers, with_minor=False):
    """Determine variants based on `classifiers`

    The classifier section of setup() is standardised but
    also hand-made, so not 100% accurate at all times.

    https://pypi.org/classifiers/

    Arguments:
        classifiers (list): Strings of classifiers
        with_minor (bool, optional): Whether to take into account
            Python minor version, or just major.
            E.g. python-2 versus python-2.6

    """

    # Only one of these may exist per install
    variants = {
        "os": None,
        "platform": None,
        "arch": None,
        "python": None,
    }

    py = {
        "2": False,
        "3": False,
    }

    def _on_operating_system(cfr):
        if cfr == "os independent":
            return

        # Operating System :: Microsoft :: Windows
        if cfr.startswith("microsoft"):
            if variants["platform"]:

                # This distribution is deemed cross-platform
                variants.pop("platform")
                return

            variants["platform"] = "windows"

            # TODO: Double-check that the versions
            # are actually this correlated to the
            # Windows product version;
            # i.e. is Windows 8 really version 8?
            if cfr.endswith("windows 10"):
                variants["os"] = "10"

            elif cfr.endswith("windows 8"):
                variants["os"] = "8"

            elif cfr.endswith("windows 7"):
                variants["os"] = "7"

        # Operating System :: posix :: linux
        if cfr.startswith("posix") or cfr.endswith("linux"):
            if variants["platform"]:

                # This distribution is deemed cross-platform
                variants.pop("platform")
                return

            variants["platform"] = "linux"

            if platform_.name == "linux":
                # The classifier merey says "Linux"
                # It doesn't contain the flavour of Linux
                # is being referred to. So here we convert
                # the generic "Linux" to whatever the current
                # os is. Not 100% clean, as it would
                # install to e.g. CentOS when really the
                # package author meant Ubuntu, but there is
                # no way for them to communicate that to us.
                variants["os"] = platform_.os

    def _on_programming_language(cfr):
        try:
            language, ver = cfr.split("::", 1)
        except ValueError:
            # Programming Language :: Python
            return

        if language != "python":
            return

        # Python :: 3 :: Only
        if ver.endswith("::only"):
            # making life easy
            version, _ = ver.split("::")
            py[version] = True
            return

        # E.g. :: Implementation :: PyPy
        if "." not in ver:
            return

        try:
            major = ver.split(".", 1)[0]
        except ValueError:
            major = ver

        if major == "2":
            py["2"] = True

        if major == "3":
            py["3"] = True

    for cfr in classifiers:
        cfr = cfr.lower()  # case-insensitive
        cfr = cfr.replace(" :: ", "::")
        cfr = cfr.replace(" ::", "::")
        cfr = cfr.replace(":: ", "::")
        key, value = cfr.split("::", 1)

        if key == "operating system":
            _on_operating_system(value)

        elif key == "programming language":
            _on_programming_language(value)

        else:
            # Not relevant
            pass

    if py["2"] and py["3"]:
        variants["python"] = None

    elif py["2"]:
        variants["python"] = "2"

    elif py["3"]:
        variants["python"] = "3"

    return [
        k + "-" + variants[k]

        # Order is important
        for k in ("platform",
                  "arch",
                  "os",
                  "python")

        if variants[k] is not None
    ]


def wheel_to_variants(wheel):
    """Parse WHEEL file of `distribution` as per PEP427

    https://www.python.org/dev/peps/pep-0427/#file-contents

    Arguments:
        wheel (str): Contents of a WHEEL file

    Returns:
        variants (dict): With keys {"platform", "os", "python"}

    """

    variants = {
        "platform": None,
        "os": None,
        "python": None,
    }

    py = {
        "2": False,
        "3": False,
        "version": [],
    }

    for line in wheel.splitlines():
        line = line.rstrip()

        if not line:
            # Empty lines are allowed
            continue

        line = line.replace(" ", "")
        key, value = line.lower().split(":")

        if key == "root-is-purelib" and value == "false":
            variants["platform"] = platform_.name

        if key == "tag":
            # May occur multiple times
            #
            # Example:
            #   py2-none-any
            #   py3-none-any
            #   cp36-cp36m-win_amd64
            #
            py_tag, abi_tag, plat_tag = value.split("-")
            major_ver = py_tag[2]

            py["version"] += [major_ver]
            py[major_ver] = True

            if plat_tag != "any":
                # We could convert e.g. `win_amd64` to a Rez platform
                # and os version, such as `platform-windows` and
                # `os-windows.10.0.1800` but there is no correlation
                # between these tags and the exact version or
                # distribution of the parent system.

                # So instead, it's safe to assume that if this package
                # was provided to Rez by pip, it must be specific to the
                # currently running platform and os.
                variants["os"] = platform_.os  # e.g. windows-10.0.1800
                variants["platform"] = platform_.name  # e.g. windows

                minor_version = py_tag[3]  # e.g. cp27
                py["version"] += [minor_version]

    if py["2"] and py["3"]:
        variants["python"] = None
    else:
        variants["python"] = ".".join(py["version"])

    return [
        k + "-" + variants[k]

        # Order is important
        for k in ("platform",
                  "os",
                  "python")

        if variants[k] is not None
    ]


_verbose = config.debug("package_release")


def _log(msg):
    if _verbose:
        print_debug(msg)


def _get_dependencies(requirement, distributions):
    def get_distrubution_name(pip_name):
        pip_to_rez_name = pip_name.lower().replace("-", "_")
        for dist in distributions:
            _name, _ = parse_name_and_version(dist.name_and_version)
            if _name.replace("-", "_") == pip_to_rez_name:
                return dist.name.replace("-", "_")
        return pip_to_rez_name

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
