from rez.packages_ import get_latest_package
from rez.vendor.version.version import Version
from rez.vendor.enum.enum import Enum
from rez.resolved_context import ResolvedContext
from rez.utils.logging_ import print_debug
from rez.exceptions import BuildError, PackageFamilyNotFoundError, \
    PackageNotFoundError, convert_errors
from rez.config import config
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


def pip_install_package(source_name, pip_version=None, python_versions=None,
                        mode=InstallMode.min_deps):
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
    """

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

    tmpdir = mkdtemp(suffix="-rez", prefix="pip-")
    packages = {}

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

    # download package and dependency archives
    dl_path = os.path.join(tmpdir, "download")
    os.mkdir(dl_path)
    archives = _download_packages(source_name,
                                  context=context,
                                  tmpdir=dl_path,
                                  no_deps=(mode == InstallMode.no_deps))

    print ("\ninstalling packages in the following order:\n"
           + '\n'.join(os.path.basename(x) for x in archives))

    # iterate over archives and build/install each, starting from those with no
    # dependencies and moving up until we install the target package last
    for archive in archives:
        _install_from_archive(archive=archive, pip_req=pip_req, py_reqs=py_reqs,
                              mode=mode)

    # cleanup
    shutil.rmtree(tmpdir)


def _install_from_archive(archive, pip_req, py_reqs, mode):
    pass


def _download_packages(source_name, context, tmpdir, no_deps):
    """
    Returns:
        list of str: List of downloaded archives, in dependency order.
    """
    archives_path = os.path.join(tmpdir, "archives")
    cache_path = os.path.join(tmpdir, "cache")
    os.mkdir(archives_path)
    os.mkdir(cache_path)

    cmd_base = ["pip", "install", "--cache-dir=%s" % cache_path]

    # download archives
    cmd = cmd_base + ["--download=%s" % archives_path]
    if no_deps:
        cmd.append("--no-deps")
    cmd.append(source_name)
    _cmd(context=context, command=cmd)

    archive_names = os.listdir(archives_path)

    if no_deps:  # nothing more to do
        archive_name = archive_names[0]
        archive = os.path.join(archives_path, archive_name)
        return [archive]

    # re-download each archive, with deps. From this we can infer the dependency
    # order. Since we use the same cache, nothing is actually re-downloaded.
    dependencies = {}
    deps_path = os.path.join(tmpdir, "deps")
    os.mkdir(deps_path)

    for archive_name in archive_names:
        depsdir = os.path.join(deps_path, archive_name)
        os.mkdir(depsdir)

        archive = os.path.join(archives_path, archive_name)
        cmd = cmd_base + ["--download=%s" % depsdir, archive]
        _cmd(context=context, command=cmd, quiet=(not _verbose))

        deps = set(os.listdir(depsdir))
        deps.remove(archive_name)
        dependencies[archive_name] = deps

    # infer dependency order from dependencies map. We need this in order to
    # know the build order we have to follow.
    archives = []

    while dependencies:
        leaf_archives = [k for k, v in dependencies.iteritems() if not v]

        if not leaf_archives:
            raise BuildError("Cyclic dependency detected in packages: %s"
                             % leaf_archives)

        for leaf_archive in leaf_archives:
            archives.append(leaf_archive)
            del dependencies[leaf_archive]

        rm_deps = set(leaf_archives)
        for deps in dependencies.itervalues():
            deps -= rm_deps

    archives = [os.path.join(archives_path, x) for x in archives]
    return archives


def _cmd(context, command, quiet=False):
    cmd_str = ' '.join(quote(x) for x in command)
    _log("running: %s" % cmd_str)

    stdout_ = subprocess.PIPE if quiet else None
    p = context.execute_shell(command=command, block=False,
                              stdout=stdout_, stderr=subprocess.PIPE)
    _, err = p.communicate()

    if p.returncode:
        raise BuildError("Failed to download source with pip:\n"
                         "Command: %s\n"
                         "Error: %s"
                         % (cmd_str, err))


_verbose = config.debug("package_release")


def _log(msg):
    if _verbose:
        print_debug(msg)
