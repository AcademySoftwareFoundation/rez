from rez.packages_ import get_latest_package
from rez.vendor.version.version import Version
from rez.resolved_context import ResolvedContext
from tempfile import mkdtemp
import os.path
import os


def pip_install_package(source_name, pip_version=None, python_versions=None,
                        no_deps=False, install_newer_deps=False):
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
        no_deps (bool): If True, don't install dependencies.
        install_newer_deps (bool): If True, newer package dependencies will be
            installed, even if existing rez package versions already exist that
            already satisfy the package's dependencies.
    """
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
        major_minor_ver = package.version[:2]
        py_req = "python-%s" % str(major_minor_ver)
        py_reqs.append(py_req)

    tmpdir = mkdtemp(suffix="-rez", prefix="pip-")
    packages = {}

    # use pip + latest python to perform common operations
    request = [pip_req, py_reqs[-1]]
    context = ResolvedContext(request)

    # download package and dependency archives
    dl_path = os.path.join(tmpdir, "download")
    os.mkdir(dl_path)
    primary_name = _download_packages(source_name,
                                      context=context,
                                      tmpdir=dl_path,
                                      no_deps=no_deps)

    # build each so we can extract dependencies and determine if they are
    # platform-specific (ie if they contain .so or similar)
    tmp_installs_path = os.path.join(tmpdir, "install")
    os.mkdir(tmp_installs_path)

    for name in os.listdir(dl_path):
        filepath = os.path.join(dl_path, name)
        tmp_install_path = os.path.join(tmp_installs_path, name)
        os.mkdir(tmp_install_path)

        metadata = _analyse_package(context, filepath, tmp_install_path)
        metadata["primary"] = (name == primary_name)
        packages[metadata["package_name"]] = metadata

    # sort as reverse dependency tree, we need to install from bottom of tree
    # up, since a rez-release must have rez package dependencies present
    package_list = _get_install_list(packages, install_newer_deps)

    # perform a rez-release on each package
    tmp_rezbuilds_path = os.path.join(tmpdir, "rez-build")
    os.mkdir(tmp_rezbuilds_path)

    for package in package_list:
        package_name = package["package_name"]
        tmp_rezbuild_path = os.path.join(tmp_rezbuilds_path, package_name)

        _rez_release_package(package,
                             pip_requirement=pip_req,
                             python_requirements=py_reqs,
                             tmpdir=tmp_rezbuild_path)


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
