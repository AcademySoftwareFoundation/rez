from __future__ import print_function

import shutil
import os.path


def build(source_path, build_path, install_path, targets):

    def _copy(src, dest):
        print("copying %s to %s..." % (src, dest))
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    # build
    src = os.path.join(source_path, "build_util")
    dest = os.path.join(build_path, "python", "build_util")
    _copy(src, dest)

    if "install" not in (targets or []):
        return

    # install
    src = os.path.join(build_path, "python")
    dest = os.path.join(install_path, "python")
    _copy(src, dest)


if __name__ == '__main__':
    import os, sys
    build(
        source_path=os.environ['REZ_BUILD_SOURCE_PATH'],
        build_path=os.environ['REZ_BUILD_PATH'],
        install_path=os.environ['REZ_BUILD_INSTALL_PATH'],
        targets=sys.argv[1:]
    )


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
