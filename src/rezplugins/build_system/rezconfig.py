# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
