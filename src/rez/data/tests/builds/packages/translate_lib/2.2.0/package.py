name = "translate_lib"

version = "2.2.0"

authors = ["axl.rose"]

description = "A simple C++ library with minimal dependencies."

def commands():
    import platform

    env.CMAKE_MODULE_PATH.append("{root}/cmake")

    if platform.system() == "Darwin":
        env.DYLD_LIBRARY_PATH.append("{root}/lib")
    else:
        env.LD_LIBRARY_PATH.append("{root}/lib")

uuid = "38eda6e8-f162-11e0-9de0-0023ae79d988"


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
