from __future__ import print_function, absolute_import

from rez.packages import get_latest_package
from rez.vendor.version.version import Version
from rez.vendor.distlib.database import DistributionPath
from rez.vendor.enum.enum import Enum
from rez.vendor.packaging.version import Version as PackagingVersion
from rez.vendor.packaging.specifiers import Specifier
from rez.vendor.six.six import StringIO
from rez.resolved_context import ResolvedContext
from rez.utils.execution import Popen
from rez.utils.pip import get_rez_requirements, pip_to_rez_package_name, \
    pip_to_rez_version
from rez.utils.logging_ import print_debug, print_info, print_error, \
    print_warning
from rez.exceptions import BuildError, PackageFamilyNotFoundError, \
    PackageNotFoundError, RezSystemError
from rez.package_maker import make_package
from rez.config import config

import os
from pipes import quote
from pprint import pformat
import re
import shutil
import subprocess
import sys
from tempfile import mkdtemp
from textwrap import dedent


PIP_SPECIFIER = Specifier(">=19")  # rez pip only compatible with pip>=19


class InstallMode(Enum):
    # don't install dependencies. Build may fail, for example the package may
    # need to compile against a dependency. Will work for pure python though.
    no_deps = 0
    # only install dependencies that we have to. If an existing rez package
    # satisfies a dependency already, it will be used instead. The default.
    min_deps = 1


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
    found_pip_version = None
    valid_found = False

    for version in [pip_version, "latest"]:
        try:
            py_exe, found_pip_version, context = find_pip_from_context(
                python_version, pip_version=version
            )
            valid_found = _check_found(py_exe, found_pip_version)
            if valid_found:
                break
        except BuildError as error:
            print_warning(str(error))

    if not valid_found:
        import pip

        found_pip_version = pip.__version__
        py_exe = sys.executable
        print_warning("Found no pip in any python and/or pip rez packages!")
        print_warning("Falling back to pip installed in rez own virtualenv:")
        logging_arguments = (
            ("pip", found_pip_version, pip.__file__),
            ("python", ".".join(map(str, sys.version_info[:3])), py_exe),
        )
        for warn_args in logging_arguments:
            print_warning("%10s: %s (%s)", *warn_args)

    if not _check_found(py_exe, found_pip_version, log_invalid=False):
        message = "pip{specifier} is required! Please update your pip."
        raise RezSystemError(message.format(specifier=PIP_SPECIFIER))

    return py_exe, context


def find_python_in_context(context):
    """Find Python executable within the given context.

    Args:
        context (ResolvedContext): Resolved context with Python and pip.
        name (str): Name of the package for Python instead of "python".
        default (str): Force a particular fallback path for Python executable.

    Returns:
        str or None: Path to Python executable, if any.
    """

    # Create a copy of the context with systems paths removed, so we don't
    # accidentally find a system python install.
    #
    context = context.copy()
    context.append_sys_path = False  # GitHub nerdvegas/rez/issue/826

    python_package = context.get_resolved_package("python")
    assert python_package

    # look for (eg) python3.7, then python3, then python
    name_template = "python{}"
    for trimmed_version in map(python_package.version.trim, [2, 1, 0]):
        exe_name = name_template.format(trimmed_version)
        py_exe_path = context.which(exe_name)
        if py_exe_path:
            return py_exe_path

    return None


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
            raise BuildError("Found no python rez package.")

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

    py_exe = find_python_in_context(context)

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
        "Found pip-%s inside %s. Will use it via %s",
        pip_version,
        package.uri,
        py_exe
    )

    return py_exe, pip_version, context


def pip_install_package(source_name, pip_version=None, python_version=None,
                        mode=InstallMode.min_deps, release=False, prefix=None,
                        extra_args=None):
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
        extra_args (List[str]): Additional options to the pip install command.

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

    targetpath = mkdtemp(suffix="-rez", prefix="pip-")

    if context and config.debug("package_release"):
        buf = StringIO()
        print("\n\npackage download environment:", file=buf)
        context.print_info(buf)
        _log(buf.getvalue())

    # Build pip commandline
    cmd = [py_exe, "-m", "pip", "install"]

    _extra_args = extra_args or config.pip_extra_args or []

    if "--no-use-pep517" not in _extra_args:
        cmd.append("--use-pep517")

    if not _option_present(_extra_args, "-t", "--target"):
        cmd.append("--target=%s" % targetpath)

    if mode == InstallMode.no_deps and "--no-deps" not in _extra_args:
        cmd.append("--no-deps")

    cmd.extend(_extra_args)
    cmd.append(source_name)

    # run pip
    #
    # Note: https://github.com/pypa/pip/pull/3934. If/when this PR is merged,
    # it will allow explicit control of where to put bin files.
    #
    _cmd(context=context, command=cmd)

    # determine version of python in use
    if context is None:
        # since we had to use system pip, we have to assume system python version
        py_ver_str = '.'.join(map(str, sys.version_info))
        py_ver = Version(py_ver_str)
    else:
        python_variant = context.get_resolved_package("python")
        py_ver = python_variant.version

    # Collect resulting python packages using distlib
    distribution_path = DistributionPath([targetpath])
    distributions = list(distribution_path.get_distributions())
    dist_names = [x.name for x in distributions]

    def log_append_pkg_variants(pkg_maker):
        template = '{action} [{package.qualified_name}] {package.uri}{suffix}'
        actions_variants = [
            (
                print_info, 'Installed',
                installed_variants, pkg_maker.installed_variants or [],
            ),
            (
                print_debug, 'Skipped',
                skipped_variants, pkg_maker.skipped_variants or [],
            ),
        ]
        for print_, action, variants, pkg_variants in actions_variants:
            for variant in pkg_variants:
                variants.append(variant)
                package = variant.parent
                suffix = (' (%s)' % variant.subpath) if variant.subpath else ''
                print_(template.format(**locals()))

    # get list of package and dependencies
    for distribution in distributions:
        # convert pip requirements into rez requirements
        rez_requires = get_rez_requirements(
            installed_dist=distribution,
            python_version=py_ver,
            name_casings=dist_names
        )

        # log the pip -> rez requirements translation, for debugging
        _log(
            "Pip to rez requirements translation information for "
            + distribution.name_and_version
            + ":\n"
            + pformat({
                "pip": {
                    "run_requires": map(str, distribution.run_requires)
                },
                "rez": rez_requires
            })
        )

        # determine where pip files need to be copied into rez package
        src_dst_lut = _get_distribution_files_mapping(distribution, targetpath)

        # build tools list
        tools = []
        for relpath in src_dst_lut.values():
            dir_, filename = os.path.split(relpath)
            if dir_ == "bin":
                tools.append(filename)

        # Sanity warning to see if any files will be copied
        if not src_dst_lut:
            message = 'No source files exist for {}!'
            if not _verbose:
                message += '\nTry again with rez-pip --verbose ...'
            print_warning(message.format(distribution.name_and_version))

        def make_root(variant, path):
            """Using distlib to iterate over all installed files of the current
            distribution to copy files to the target directory of the rez package
            variant
            """
            for rel_src, rel_dest in src_dst_lut.items():
                src = os.path.join(targetpath, rel_src)
                dest = os.path.join(path, rel_dest)

                if not os.path.exists(os.path.dirname(dest)):
                    os.makedirs(os.path.dirname(dest))

                shutil.copyfile(src, dest)

                if _is_exe(src):
                    shutil.copystat(src, dest)

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

            distribution_metadata = distribution.metadata.todict()

            help_ = []

            if "home_page" in distribution_metadata:
                help_.append(["Home Page", distribution_metadata["home_page"]])

            if "download_url" in distribution_metadata:
                help_.append(["Source Code", distribution_metadata["download_url"]])

            if help_:
                pkg.help = help_

            if "author" in distribution_metadata:
                author = distribution_metadata["author"]

                if "author_email" in distribution_metadata:
                    author += ' ' + distribution_metadata["author_email"]

                pkg.authors = [author]

        log_append_pkg_variants(pkg)

    # cleanup
    shutil.rmtree(targetpath)

    # print summary
    #
    if installed_variants:
        print_info("%d packages were installed.", len(installed_variants))
    else:
        print_warning("NO packages were installed.")
    if skipped_variants:
        print_warning(
            "%d packages were already installed.",
            len(skipped_variants),
        )

    return installed_variants, skipped_variants


def _is_exe(fpath):
    return os.path.exists(fpath) and os.access(fpath, os.X_OK)


def _get_distribution_files_mapping(distribution, targetdir):
    """Get remapping of pip installation to rez package installation.

    Args:
        distribution (`distlib.database.InstalledDistribution`): The installed
            distribution
        targetdir (str): Where distribution was installed to (via pip --target)

    Returns:
        Dict of (str, str):
        * key: Path of pip installed file, relative to `targetdir`;
        * value: Relative path to install into rez package.
    """
    def get_mapping(rel_src):
        topdir = rel_src.split(os.sep)[0]

        # Special case - dist-info files. These are all in a '<pkgname>-<version>.dist-info'
        # dir. We keep this dir and place it in the root dir of the rez package.
        #
        if topdir.endswith(".dist-info"):
            return (rel_src, rel_src)

        # Remapping of other installed files according to manifest
        if topdir == os.pardir:
            for remap in config.pip_install_remaps:
                path = remap['record_path']
                if re.search(path, rel_src):
                    pip_subpath = re.sub(path, remap['pip_install'], rel_src)
                    rez_subpath = re.sub(path, remap['rez_install'], rel_src)
                    return (pip_subpath, rez_subpath)

            tokenised_path = rel_src.replace(os.pardir, '{pardir}')
            tokenised_path = tokenised_path.replace(os.sep, '{sep}')
            dist_record = '{dist.name}-{dist.version}.dist-info{os.sep}RECORD'
            dist_record = dist_record.format(dist=distribution, os=os)

            try_this_message = r"""
            Unknown source file in {0}! '{1}'

            To resolve, try:

            1. Manually install the pip package using 'pip install --target'
               to a temporary location.
            2. See where '{1}'
               actually got installed to by pip, RELATIVE to --target location
            3. Create a new rule to 'pip_install_remaps' configuration like:

                {{
                    "record_path": r"{2}",
                    "pip_install": r"<RELATIVE path pip installed to in 2.>",
                    "rez_install": r"<DESTINATION sub-path in rez package>",
                }}

            4. Try rez-pip install again.

            If path remapping is not enough, consider submitting a new issue
            via https://github.com/nerdvegas/rez/issues/new
            """.format(dist_record, rel_src, tokenised_path)
            print_error(dedent(try_this_message).lstrip())

            raise IOError(
                89,  # errno.EDESTADDRREQ : Destination address required
                "Don't know what to do with relative path in {0}, see "
                "above error message for".format(dist_record),
                rel_src,
            )

        # At this point the file should be <pkg-name>/..., so we put
        # into 'python' subdir in rez package.
        #
        rel_dest = os.path.join("python", rel_src)
        return (rel_src, rel_dest)

    # iterate over pip installed files
    result = {}
    for installed_file in distribution.list_installed_files():
        rel_src_orig = os.path.normpath(installed_file[0])
        rel_src, rel_dest = get_mapping(rel_src_orig)

        src_filepath = os.path.join(targetdir, rel_src)
        if not os.path.exists(src_filepath):
            print_warning(
                "Skipping non-existent source file: %s (%s)",
                src_filepath, rel_src_orig
            )
            continue

        result[rel_src] = rel_dest

    return result


def _option_present(opts, *args):
    for opt in opts:
        for arg in args:
            if opt == arg or opt.startswith(arg + '='):
                return True
    return False


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


def _check_found(py_exe, version_text, log_invalid=True):
    """Check the Python and pip version text found.

    Args:
        py_exe (str or None): Python executable path found, if any.
        version_text (str or None): Pip version found, if any.
        log_invalid (bool): Whether to log messages if found invalid.

    Returns:
        bool: Python is OK and pip version fits against ``PIP_SPECIFIER``.
    """
    is_valid = True
    message = "Needs pip%s, but found '%s' for Python '%s'"

    if version_text is None or not py_exe:
        is_valid = False
        if log_invalid:
            print_debug(message, PIP_SPECIFIER, version_text, py_exe)

    elif PackagingVersion(version_text) not in PIP_SPECIFIER:
        is_valid = False
        if log_invalid:
            print_warning(message, PIP_SPECIFIER, version_text, py_exe)

    return is_valid


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
