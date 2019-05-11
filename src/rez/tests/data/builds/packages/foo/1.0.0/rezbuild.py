from __future__ import print_function
from build_util import build_directory_recurse, check_visible
import os.path


def build(source_path, build_path, install_path, targets):

    # build requirement 'floob' should be visible
    check_visible("foo", "floob")
    import floob
    print(floob.hello())

    # do the build
    if "install" not in (targets or []):
        install_path = None

    build_directory_recurse(src_dir="foo",
                            dest_dir=os.path.join("python", "foo"),
                            source_path=source_path,
                            build_path=build_path,
                            install_path=install_path)


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
