import os


cmake = {
    # The name of the CMake build system to use, valid options are
    # eclipse, make, xcode and codeblocks.
    "build_system": "make",

    # The name of the CMake build target to use, valid options are Debug,
    # Release and RelWithDebInfo.
    "build_target": "Release",

    # A list of default arguments to be passed to the cmake binary.
    "cmake_args": [
        '-Wno-dev',
        '-DCMAKE_ECLIPSE_GENERATE_SOURCE_PROJECT=TRUE',
        '-D_ECLIPSE_VERSION=4.3',
        '--no-warn-unused-cli',
    ],

    # Optionally specify an explicit cmake executable to use for building.
    "cmake_binary": None,

    # Optionally specify an explicit make executable to use for building. If
    # not specified, this is determined automatically based on `build_system`.
    "make_binary": None,

    # If True, install pyc files when the 'rez_install_python' macro is used.
    "install_pyc": True,
}

if os.name != "posix":
    cmake["build_system"] = "nmake"


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
