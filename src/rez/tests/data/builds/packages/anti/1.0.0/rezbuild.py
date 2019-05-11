from __future__ import print_function
from build_util import build_directory_recurse, check_visible

def build(source_path, build_path, install_path, targets):

    # normal requirement 'foo' should be visible
    check_visible('anti', 'build_util')

    check_visible('anti', 'floob')
    import floob
    floob.hello()

    try:
        import loco
        raise Exception('loco should not be here')
    except ImportError:
        print('Intentionally raising an ImportError since loco should not be available')
        pass


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
