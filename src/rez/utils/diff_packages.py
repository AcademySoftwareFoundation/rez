from __future__ import print_function

from rez.packages import iter_packages
from rez.config import config
from rez.plugin_managers import plugin_manager
from rez.exceptions import RezError
from tempfile import mkdtemp
from subprocess import Popen
import os.path


def diff_packages(pkg1, pkg2=None):
    """Invoke a diff editor to show the difference between the source of two
    packages.

    Args:
        pkg1 (`Package`): Package to diff.
        pkg2 (`Package`): Package to diff against. If None, the next most recent
            package version is used.
    """
    if pkg2 is None:
        it = iter_packages(pkg1.name)
        pkgs = [x for x in it if x.version < pkg1.version]
        if not pkgs:
            raise RezError("No package to diff with - %s is the earliest "
                           "package version" % pkg1.qualified_name)
        pkgs = sorted(pkgs, key=lambda x: x.version)
        pkg2 = pkgs[-1]

    def _check_pkg(pkg):
        if not (pkg.vcs and pkg.revision):
            raise RezError("Cannot diff package %s: it is a legacy format "
                           "package that does not contain enough information"
                           % pkg.qualified_name)

    _check_pkg(pkg1)
    _check_pkg(pkg2)
    path = mkdtemp(prefix="rez-pkg-diff")
    paths = []

    for pkg in (pkg1, pkg2):
        print("Exporting %s..." % pkg.qualified_name)
        path_ = os.path.join(path, pkg.qualified_name)
        vcs_cls_1 = plugin_manager.get_plugin_class("release_vcs", pkg1.vcs)
        vcs_cls_1.export(revision=pkg.revision, path=path_)
        paths.append(path_)

    difftool = config.difftool
    print("Opening diff viewer %s..." % difftool)

    with Popen([difftool] + paths) as p:
        p.wait()


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
