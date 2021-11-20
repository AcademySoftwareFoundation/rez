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
# rez_install_python
#
# Macro for building and installing python files for rez projects. This is the same as install_python,
# except that it ensures that a python package is being used, and uses the appropriate python binary.
#
# Usage:
# rez_install_python(<label>
#                    FILES <py_files>
#                    [RELATIVE <rel_path>]
#                    [LOCAL_SYMLINK]
#                    DESTINATION <rel_install_dir>)
#


if(NOT REZ_BUILD_ENV)
	message(FATAL_ERROR "RezInstallPython requires that RezBuild have been included beforehand.")
endif(NOT REZ_BUILD_ENV)


include(Utils)
include(InstallPython)


macro (rez_install_python)

	#
	# check that 'python' is in the environment. All 'python' packages should expose a 'rez-python'
	# binary (whether that be symlink/wrapper script etc), the following build command relies
	# on this, so that the correct version of the python interpreter is used to compile.
	#

	list_contains(pyfound python ${REZ_BUILD_ALL_PKGS})
	if(NOT pyfound)
		message(FATAL_ERROR "a version of python must be listed as a requirement when using the 'rez_install_python' macro. Packages for this build are: ${REZ_BUILD_ALL_PKGS}")
	endif(NOT pyfound)

	install_python(${ARGV} BIN python)

endmacro (rez_install_python)
