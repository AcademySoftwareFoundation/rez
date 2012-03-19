#
# rez_install_python
#
# Macro for building and installing python files for rez projects. This is the same as install_python,
# except that it ensures that a python package is being used, and uses the appropriate python binary.
#
# Usage:
# rez_install_python(<label> FILES <py_files> [RELATIVE <rel_path>] DESTINATION <rel_install_dir>)
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

	# NOTE: 'rezpy' correlates with the python executable that the 'python' package in the
	# current environment has exposed. 'rezpy' is just the name of this binary that Rez sets
	# up in its bootstrap python package... if you don't like it then you can change it,
	# but make sure you change it in your python package, as well as here.
	install_python(${ARGV} BIN rezpy)

endmacro (rez_install_python)










#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
