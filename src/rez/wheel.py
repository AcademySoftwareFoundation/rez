"""Install pip-package are rez-package

Algorithm:
    1. Install with pip --install six --target STAGING_DIR
    2. Scan STAGING_DIR for installed packages and report
    3. Convert pip-package requirements to rez-requirements
    4. Convert pip-package to rez-package

"""

from rez.vendor.distlib import DistlibException
from rez.vendor.distlib.database import DistributionPath
from rez.vendor.distlib.markers import interpret
from rez.vendor.distlib.util import parse_name_and_version
from rez.utils.logging_ import print_debug
from rez.package_maker__ import PackageMaker
from rez.config import config
from rez.vendor.six import six
from rez.utils.platform_ import platform_
from rez.utils.filesystem import retain_cwd

import os
import errno
import shutil
import logging
import tempfile
import subprocess

# Public API
__all__ = [
    "install",
    "download",
    "convert",
    "deploy",
]

# Mute unnecessary messages
logging.getLogger("rez.vendor.distlib").setLevel(logging.CRITICAL)
_basestring = six.string_types[0]
_files = {}


def install(names,
            prefix=None,
            no_deps=False,
            release=False,
            variants=None,
            index_url=None):
    """Convenience function to below functions

    Arguments:
        names (list): pip-formatted package names, e.g. six=1.12
        prefix (str, optional): Absolute path to destination repository
        no_deps (bool, optional): Do not install dependencies,
            equivalent to pip --no-deps
        release (bool, optional): Install onto REZ_RELEASE_PACKAGES_PATH
        variants (list, optional): Override variants detected by WHEEL
        index (str, optional): Override PyPI index. This should point to a
            repository compliant with PEP 503 (the simple repository API)
            or a local directory laid out in the same format.

    """

    assert prefix is None or isinstance(prefix, _basestring), (
        "%s was not str" % prefix)
    assert isinstance(names, (tuple, list)), "%s was not list or tuple" % names

    tempdir = tempfile.mkdtemp(suffix="-rez", prefix="pip-")

    distributions = download(
        names,
        tempdir=tempdir,
        no_deps=no_deps,
        index_url=index_url,
    )

    packagesdir = prefix or (
        config.release_packages_path if release
        else config.local_packages_path
    )

    new, existing = list(), list()
    for dist in distributions:
        package = convert(dist, variants=variants)

        if exists(package, packagesdir):
            existing.append(package)
        else:
            new.append(package)

    if not new:
        return []

    for package in new:
        deploy(package, path=packagesdir)

    shutil.rmtree(tempdir)
    return new


def download(names, tempdir=None, no_deps=False, index_url=None):
    """Gather pip packages in `tempdir`

    Arguments:
        names (list): Names of packages to install, in pip-format,
            e.g. ["six==1"]
        tempdir (str, optional): Absolute path to where pip packages go until
            they've been installed as Rez packages, defaults to the cwd
        no_deps (bool, optional): Equivalent to pip --no-deps, default to False
        index_url (str, optional): Custom PyPI index

    Returns:
        distributions (list): Downloaded distlib.database.InstalledDistribution

    Raises:
        OSError: On anything gone wrong with subprocess and pip

    """

    assert isinstance(names, (list, tuple)), (
        "%s was not a tuple or list" % names
    )
    assert all(isinstance(name, _basestring) for name in names), (
        "%s contained non-string" % names
    )

    tempdir = tempdir or os.getcwd()

    # Build pip commandline
    cmd = [
        "python", "-m", "pip", "install",
        "--target", tempdir,

        # Only ever consider wheels, anything else is ancient
        "--use-pep517",

        # Handle case where the Python distribution used alongside
        # pip already has a package installed in its `site-packages/` dir.
        "--ignore-installed",

        # rez pip users don't have to see this
        "--disable-pip-version-check",
    ]

    if index_url:
        cmd += ["--index-url", index_url]

    else:
        # Prevent user-settings from interfering with install
        cmd += ["--isolated"]

    if no_deps:
        # Delegate the installation of dependencies to the user
        # This is important, as each dependency may have different
        # requirements of its own, and variants to go with it.
        cmd += ["--no-deps"]

    cmd += names

    popen = subprocess.Popen(cmd,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             universal_newlines=True)

    output = []
    for line in iter(popen.stdout.readline, ""):

        if line.startswith("DEPRECATION"):
            # Mute warnings about Python 2 being deprecated.
            # It's out-of-band for the casual Rez user.
            continue

        output.append(line.rstrip())

    popen.wait()

    if popen.returncode != 0:
        raise OSError(
            # pip output -------
            # Some error here
            # ------------------
            "\n".join([
                "pip output ".ljust(70, "-"),
                "",
                "\n".join(output),
                "",
                "-" * 70,
            ])
        )

    distribution_path = DistributionPath([tempdir])
    distributions = list(distribution_path.get_distributions())

    return sorted(
        distributions,

        # Upper-case characters typically come first
        key=lambda d: d.name.lower()
    )


def exists(package, path):
    """Does `distribution` already exists as a Rez-package in `path`?

    Arguments:
        package (rez.Package):
        path (str): Absolute path of where to look

    """

    try:
        variant = next(package.iter_variants())
    except StopIteration:
        return False

    return variant.install(path, dry_run=True) is not None


def convert(distribution, variants=None):
    """Make a Rez package out of `distribution`

    Arguments:
        distribution (distlib.database.InstalledDistribution): Source
        variants (list, optional): Explicitly provide variants, defaults
            to automatically detecting the correct variants using the
            WHEEL metadata of `distribution`.

    """

    name, _ = parse_name_and_version(distribution.name_and_version)
    name = _rez_name(distribution.name[:len(name)])

    # determine variant requirements
    variants_ = variants or []

    if not variants_:
        wheen_fname = os.path.join(distribution.path, "WHEEL")
        with open(wheen_fname) as f:
            variants_.extend(wheel_to_variants(f.read()))

    requirements = _pip_to_rez_requirements(distribution)

    maker = PackageMaker(name)
    maker.version = distribution.version

    if requirements:
        maker.requires = requirements

    if distribution.metadata.summary:
        maker.description = distribution.metadata.summary

    if variants_:
        maker.variants = [variants_]

    maker.commands = '\n'.join([
        "env.PYTHONPATH.append('{root}/python')"
    ])

    # Store files from distribution for deployment
    files = list()
    for fname, md5, size in distribution.list_installed_files():
        dist_info = distribution.path
        dirname = os.path.dirname(dist_info)
        abspath = os.path.join(dirname, fname)
        normpath = os.path.normpath(abspath)

        if not os.path.exists(normpath):
            print("WARNING: %s didn't exist" % normpath)
            continue

        files += [normpath]

    _files[name] = files

    package = maker.get_package()
    return package


def deploy(package, path):
    """Deploy `distribution` as `package` at `path`

    Arguments:
        package (rez.Package): Source package
        path (str): Path to install directory, e.g. "~/packages"

    """

    stagingsep = "".join([os.path.sep, "rez_staging", os.path.sep])

    def make_root(variant, root):
        for src in _files.pop(package.name):
            dst = src.split(stagingsep)[1]
            dst = os.path.join(path, dst)
            dst = os.path.normpath(dst)

            if not os.path.exists(os.path.dirname(dst)):
                os.makedirs(os.path.dirname(dst))

            shutil.copyfile(src, dst)

    variant = next(package.iter_variants())
    variant_ = variant.install(path)

    root = variant_.root
    if make_root and root:
        try:
            os.makedirs(root)
        except OSError as e:
            if e.errno == errno.EEXIST:
                # That's ok
                pass
            else:
                raise

    with retain_cwd():
        os.chdir(root)
        make_root(variant_, root)

    return variant_


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

        if key == "wheel-version":
            if value[0] != "1":
                raise ValueError("Unsupported WHEEL format")

        if key == "root-is-purelib" and value == "false":
            variants["platform"] = platform_name()

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
                # `os-windows.10.0.1800` but it's safe to assume that if
                # this package was provided by pip, it must be specific
                # to the currently running platform and os.

                variants["os"] = os_name()
                variants["platform"] = platform_name()  # e.g. windows

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


def os_name():
    """Return pip-compatible OS, e.g. windows-10.0 and Debian-7.6"""
    # pip packages are no more specific than minor/major of an os
    # E.g. windows-10.0.18362 -> windows-10.0
    return ".".join(platform_.os.split(".")[:2])


def platform_name():
    return platform_.name


def python_version():
    import subprocess
    from rez.status import status
    context = status.context

    try:
        # Use supplied Python
        package = context.get_resolved_package("python")
        return str(package.version)
    except AttributeError:
        # In a context, but no Python was found
        pass

    # Try system Python
    popen = subprocess.Popen(
        "python --version",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=10 ** 4,  # Enough to capture the version
        shell=True,
    )

    if popen.wait() == 0:
        version = popen.stdout.read().rstrip()
        version = version.split()[-1]  # Python 2.7.11
        return version + " (system)"  # 2.7.11


def pip_version():
    import subprocess
    from rez.status import status
    context = status.context

    try:
        # Use supplied Python
        package = context.get_resolved_package("pip")
        return str(package.version)
    except AttributeError:
        # In a context, but no Python was found
        pass

    # Try system Python
    popen = subprocess.Popen(
        "python -c \"import pip;print(pip.__version__)\"",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=10 ** 4,  # Enough to capture the version
        shell=True,
    )

    if popen.wait() == 0:
        version = popen.stdout.read().rstrip()
        return version + " (system)"


_verbose = config.debug("package_release")


def _log(msg):
    if _verbose:
        print_debug(msg)


def _rez_name(pip_name):
    return pip_name.replace("-", "_")


def _get_dependencies(requirement):

    requirements = ([requirement] if isinstance(requirement, basestring)
                    else requirement["requires"])

    result = []
    for package in requirements:
        if "(" in package:
            try:
                name, version = parse_name_and_version(package)
                version = version.replace("==", "")
                name = _rez_name(name)
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
                name = _rez_name(name)

            result.append("-".join([name, version]))
        else:
            name = _rez_name(package)
            result.append(name)

    return result


def _pip_to_rez_requirements(distribution):
    """Convert pip-requirements --> rez-requirements"""

    requirements = []
    for req in (distribution.metadata.run_requires or []):
        if "environment" in req:
            if interpret(req["environment"]):
                requirements += _get_dependencies(req)

        elif "extra" in req:
            # TODO: Handle optional requirements
            # e.g. requests[security]
            pass

        else:
            requirements += _get_dependencies(req)

    return requirements


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
