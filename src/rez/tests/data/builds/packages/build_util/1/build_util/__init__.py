from __future__ import print_function
import shutil
import os.path



def build_directory_recurse(src_dir, dest_dir, source_path, build_path,
                            install_path=None):

    def _copy(src, dest):
        print("copying %s to %s..." % (src, dest))
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    # build
    src = os.path.join(source_path, src_dir)
    dest = os.path.join(build_path, dest_dir)
    _copy(src, dest)

    if not install_path:
        return

    # install
    src = os.path.join(build_path, dest_dir)
    dest = os.path.join(install_path, dest_dir)
    _copy(src, dest)


def check_visible(module, try_module):
    try:
        __import__(try_module, {})
    except ImportError as e:
        raise Exception(("%s's rezbuild.py should have been able to access "
                        "%s! Error: %s") % (module, try_module, str(e)))


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
