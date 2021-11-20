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


#
# macro:
# rez_project
#
# Use this macro in lieu of cmake's native 'project' macro, when writing projects
# that use rez-build. The project name is not an argument to the macro - it is
# read from the package.py instead.


macro (rez_project)

    # As a Windows compiler and build environment isn't correctly setup (yet),
    # stop CMake performing automatic compiler discovery (and failing).
    if (CMAKE_SYSTEM_NAME STREQUAL "Windows")
        project(${REZ_BUILD_PROJECT_NAME} NONE)
    elseif()
        project(${REZ_BUILD_PROJECT_NAME})
    endif()

endmacro (rez_project)
