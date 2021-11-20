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
# rez_set_archive
#
# usage:
# rez_set_archive(variable RELATIVE_PATH URL)
#
# This macro checks for the existence of a file at the given relative path, under
# the path specified by the environment variable $REZ_REPO_PAYLOAD_DIR. This
# file is typically a source archive, such as a .tgz.
#
# If the file doesn't exist, an error is raised. If it does, the path is written
# to 'variable'.
#
# This macro is used by many of the packages found in the 'repository' directory.
#

macro (rez_set_archive variable RELATIVE_PATH URL)

	if(NOT DEFINED ENV{REZ_REPO_PAYLOAD_DIR})
        message(FATAL_ERROR "REZ_REPO_PAYLOAD_DIR environment variable is not set")
    endif()

    set(archive $ENV{REZ_REPO_PAYLOAD_DIR}/${RELATIVE_PATH})

    if(EXISTS "${archive}")
    	set(${variable} ${archive})
    else()
    	message(FATAL_ERROR "Archive does not exist: ${archive}. Consider downloading it from ${URL}")
    endif()

endmacro (rez_set_archive)
