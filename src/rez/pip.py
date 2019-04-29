from rez.packages_ import get_latest_package
from rez.vendor.version.version import Version
from rez.vendor.distlib import DistlibException
from rez.vendor.distlib.database import DistributionPath
from rez.vendor.distlib.markers import interpret
from rez.vendor.distlib.util import parse_name_and_version
from rez.resolved_context import ResolvedContext
from rez.utils.system import popen
from rez.utils.logging_ import print_debug, print_info, print_warning
from rez.exceptions import BuildError, PackageFamilyNotFoundError, \
    PackageNotFoundError, convert_errors
from rez.package_maker__ import make_package
from rez.config import config
from rez.utils.platform_ import platform_
from tempfile import mkdtemp
from StringIO import StringIO
from pipes import quote
import os.path
import shutil
import sys
import os


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


def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)


def run_pip_command(command_args, python_version=None):
    """Run a pip command.

    Args:
        command_args (list of str): Args to pip.

    Returns:
        `subprocess.Popen`: Pip process.
    """
    python_exe, context = find_python(python_version)
    command = [python_exe, "-m", "pip"] + list(command_args)

    if context is None:
        return popen(command)
    else:
        return context.execute_shell(command=command, block=False)


def find_python(python_version=None):
    """Find a pip exe using the given python version.

    Returns:
        2-tuple:
            str: pip executable;
            `ResolvedContext`: Context containing pip, or None if we fell back
                to system pip.
    """
    python_exe = "python"

    try:
        context = create_context(python_version)
    except BuildError as e:
        # fall back on system pip. Not ideal but at least it's something
        from rez.backport.shutilwhich import which

        python_exe = which("python")

        if python_exe:
            print_warning(
                "python rez package could not be found; system 'python' "
                "command (%s) will be used instead." % python_exe)
            context = None
        else:
            raise e

    return python_exe, context


def create_context(python_version=None):
    """Create a context containing the specific pip and python.

    Args:
        python_version (str or `Version`): Python version to use,
            or latest if None.

    Returns:
        `ResolvedContext`: Context containing pip and python.

    """

    # determine pip pkg to use for install, and python variants to install on
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

    # use specified version of python to perform pip download operations
    request = [py_req]

    with convert_errors(from_=(PackageFamilyNotFoundError,
                               PackageNotFoundError),
                        to=BuildError, msg="Cannot run - pip or python rez "
                        "package is not present"):
        context = ResolvedContext(request)

    # print pip package used to perform the install
    python_variant = context.get_resolved_package("python")
    python_package = python_variant.parent
    print_info("Using %s (%s)" % (python_package.qualified_name,
                                  python_variant.uri))

    return context


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

        # Operating System :: posix :: linux
        if cfr.startswith("posix") or cfr.endswith("linux"):
            if variants["platform"]:

                # This distribution is deemed cross-platform
                variants.pop("platform")
                return

            variants["platform"] = "linux"

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


def wheel_to_variants(distribution):
    """Parse WHEEL file of `distribution` as per PEP427

    https://www.python.org/dev/peps/pep-0427/#file-contents

    """

    variants = {
        "platform": None,
        "os": None,
        "python": None
    }

    py = {
        "2": False,
        "3": False,
    }

    wheen_fname = os.path.join(distribution.path, "WHEEL")
    with open(wheen_fname) as f:
        for line in f.readlines():
            line = line.rstrip()

            if not line:
                continue

            line = line.replace(" ", "")
            key, value = line.lower().split(":")

            if key == "root-is-purelib" and value == "false":
                variants["platform"] = platform_.name

            if key == "tag":
                # Possible combinations:
                #   py2-none-any
                #   py3-none-any
                #   cp36-cp36m-win_amd64
                py_tag, abi_tag, plat_tag = value.split("-")
                major_ver = py_tag[2]
                py[major_ver] = True

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
                  "os",
                  "python")

        if variants[k] is not None
    ]


def pip_install_package(source_name, python_version=None,
                        release=False, no_deps=False,
                        prefix=None, auto_variants=True,
                        variants=None):
    """Install a pip-compatible python package as a rez package.
    Args:
        source_name (str): Name of package or archive/url containing the pip
            package source. This is the same as the arg you would pass to
            the 'pip install' command.
        python_version (str or `Version`): Python version to use to perform the
            install, and subsequently have the resulting rez package depend on.
        prefix (str, optional): Override install location to here,
            similar to `rez build --prefix`
        no_deps (bool, optional): The `pip --no-deps` argument
        auto_variants (bool, optional): Compute variants from the PyPI
            classifiers portion of setup()
        release (bool): If True, install as a released package; otherwise, it
            will be installed as a local package.
        prefix (str, optional): Override release path with this absolute path

    Returns:
        2-tuple:
            List of `Variant`: Installed variants;
            List of `Variant`: Skipped variants (already installed).
    """

    installed_variants = []
    skipped_variants = []

    if prefix is not None:
        config.release_packages_path = prefix

    # TODO: should check if packages_path is writable
    # before continuing with pip
    #
    packages_path = (config.release_packages_path if release
                     else config.local_packages_path)

    tmpdir = mkdtemp(suffix="-rez", prefix="pip-")
    stagingdir = os.path.join(tmpdir, "rez_staging")
    stagingsep = "".join([os.path.sep, "rez_staging", os.path.sep])

    destpath = os.path.join(stagingdir, "python")

    python_exe, context = find_python(python_version)
    if context and config.debug("package_release"):
        buf = StringIO()
        print >> buf, "\n\npackage download environment:"
        context.print_info(buf)
        _log(buf.getvalue())

    # Build pip commandline
    cmd = [
        python_exe, "-m", "pip", "install",
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

    _cmd(context=context, command=cmd)

    # Collect resulting python packages using distlib
    distribution_path = DistributionPath([destpath])
    distributions = [d for d in distribution_path.get_distributions()]

    for distribution in distribution_path.get_distributions():

        requirements = []
        if distribution.metadata.run_requires:
            # Handle requirements. Currently handles
            # conditional environment based
            # requirements and normal requirements
            # TODO: Handle optional requirements?
            for requirement in distribution.metadata.run_requires:
                if "environment" in requirement:
                    if interpret(requirement["environment"]):
                        requirements.extend(_get_dependencies(
                            requirement, distributions))
                elif "extra" in requirement:
                    # Currently ignoring optional requirements
                    pass
                else:
                    requirements.extend(_get_dependencies(
                        requirement, distributions))

        tools = []
        src_dst_lut = {}
        files = distribution.list_installed_files()

        for installed_file in files:
            source_file = os.path.join(destpath, installed_file[0])
            source_file = os.path.normpath(source_file)

            if os.path.exists(source_file):
                destination_file = source_file.split(stagingsep)[1]
                exe = False

                starts_with_bin = destination_file.startswith(
                    "%s%s" % ("bin", os.path.sep)
                )

                if is_exe(source_file) and starts_with_bin:
                    _, _file = os.path.split(destination_file)
                    tools.append(_file)
                    exe = True

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
            variants_.extend(wheel_to_variants(distribution))

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
