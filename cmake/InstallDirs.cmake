#
# install_dirs_
# rez_install_dirs
#
# Macro for installing directories. Very similar to cmake's native install(DIRECTORY), but
# is more convenient to use. Files are installed as read-only. svn files (any file within
# a .svn dir) are excluded. If this macro does not provide enough fine-grain control for
# your needs, then you should use cmake's install(DIRECTORY) macro instead (and you should
# use the values REZ_FILE_INSTALL_PERMISSIONS and REZ_EXECUTABLE_FILE_INSTALL_PERMISSIONS
# to specify the permissions you want).
#
# Usage: install_dirs_(
#	<directories>
#	DESTINATION <rel_install_dir>
#	[EXECUTABLE]
# )
#

include(Utils)


# there isn't anything rez-specific here, but this matches name convention on other macros
macro (rez_install_dirs)
	install_dirs_(${ARGV})
endmacro (rez_install_dirs)


macro (install_dirs_)

	#
	# parse args
	#

	parse_arguments(INSTD "DESTINATION" "EXECUTABLE" ${ARGN})

	if(NOT INSTD_DEFAULT_ARGS)
		message(FATAL_ERROR "no directories listed in call to install_dirs_")
	endif(NOT INSTD_DEFAULT_ARGS)

	list(GET INSTD_DESTINATION 0 dest_dir)
	if(NOT dest_dir)
		message(FATAL_ERROR "need to specify DESTINATION in call to install_dirs_")
	endif(NOT dest_dir)

	if(INSTD_EXECUTABLE)
		set(perms ${REZ_EXECUTABLE_FILE_INSTALL_PERMISSIONS})
	else(INSTD_EXECUTABLE)
		set(perms ${REZ_FILE_INSTALL_PERMISSIONS})
	endif(INSTD_EXECUTABLE)

	install(DIRECTORY
		${INSTD_DEFAULT_ARGS}
		DESTINATION ${dest_dir}
		FILE_PERMISSIONS ${perms}
		PATTERN .svn EXCLUDE
	)

endmacro (install_dirs_)















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
