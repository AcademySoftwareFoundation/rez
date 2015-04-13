#
# macro:
# rez_project
#
# Use this macro in lieu of cmake's native 'project' macro, when writing projects that use rez-build. The
# project name is not an argument to the macro - it is read from the package.yaml instead.
#

macro (rez_project)

	# As a Windows compiler and build environment isn't correctly setup (yet),
	# stop CMake performing automatic compiler discovery (and failing).
    if (CMAKE_SYSTEM_NAME STREQUAL "Windows")
        project(${REZ_BUILD_PROJECT_NAME} NONE)
    elseif()
        project(${REZ_BUILD_PROJECT_NAME})
    endif()

	# this ensures there is always an 'install' target, otherwise packages with
	# an empty build will fail to install
	add_custom_target(install)

endmacro (rez_project)


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
