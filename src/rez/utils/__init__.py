import os
import sys


def reraise(exc, new_exc_cls=None, format_str=None):
    if new_exc_cls is None:
        raise

    if format_str is None:
        format_str = "%s"

    raise new_exc_cls, format_str % exc, sys.exc_info()[2]


def get_resource_file(path, *paths):
    """Get filepath to a resource file.
    """
    from rez import rez_is_compiled, module_root_path

    # check in source
    if not rez_is_compiled:
        filepath = os.path.join(module_root_path, path, *paths)
        if os.path.exists(filepath):
            return filepath

    # check in os-specific locations (eg /opt/rez, etc)
    # TODO

    # file not found
    return None


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
