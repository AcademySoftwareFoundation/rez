#
# rez_install_context
#
# This macro takes the same information that rez-config itself does (ie resolution
# mode, packages) and creates and installs a context file (including supporting
# files - .dot).
#
# 'label': just a name for the target which builds the context file.
#
# 'target': name of the context file to generate.
#
# MODE: resolution mode [default: latest]
#
# PACKAGES: packages in the context.
#
# DESTINATION: relative directory where context file will be installed to.
#
# EXTRA_COMMANDS: extra bash commands, will be added to the end of the context
#
# Usage:
# rez_install_context(<label> <target>
#	[MODE earliest|latest] [default=latest]
#	PACKAGES pkg1 pkg2 ... pkgN
#	DESTINATION <target_dir>
#	[EXTRA_COMMANDS cmd1 cmd2 ... cmdN] )
#
# Eg:
# rez_install_context(
#	context
#	foo.context
#	MODE latest
#	PACKAGES houdini-11 boost-1.37.0 rv
#	DESTINATION .
# )
#


include(Utils)

macro (rez_install_context)

	#
	# parse args
	#

	parse_arguments(INSTCTXT "MODE;PACKAGES;DESTINATION;EXTRA_COMMANDS" "" ${ARGN})

	list(GET INSTCTXT_DEFAULT_ARGS 0 label)
	if(NOT label)
		message(FATAL_ERROR "need to specify a label in call to rez_install_context")
	endif(NOT label)

	list(GET INSTCTXT_DEFAULT_ARGS 1 target)
	if(NOT target)
		message(FATAL_ERROR "need to specify a target in call to rez_install_context")
	endif(NOT target)

	list(GET INSTCTXT_MODE 0 mode)
	if(NOT mode)
		set(mode latest)
	endif(NOT mode)

	list(GET INSTCTXT_DESTINATION 0 INSTCTXT_dest_dir)
	if(NOT INSTCTXT_dest_dir)
		message(FATAL_ERROR "need to specify DESTINATION in call to rez_install_context")
	endif(NOT INSTCTXT_dest_dir)

	if(NOT INSTCTXT_PACKAGES)
		message(FATAL_ERROR "no packages listed in call to rez_install_context")
	endif(NOT INSTCTXT_PACKAGES)


	#
	# build and install context.
	#

	string(REPLACE ";" " ; " INSTCTXT_EXTRA_COMMANDS2 "${INSTCTXT_EXTRA_COMMANDS}")
	string(TOUPPER ${REZ_BUILD_PROJECT_NAME} uproj)

	list_to_string(INSTCTXT_PACKAGES2 INSTCTXT_PACKAGES)

	add_custom_command(
		OUTPUT
			${INSTCTXT_dest_dir}/${target}
			${INSTCTXT_dest_dir}/${target}.dot

		COMMAND ${CMAKE_COMMAND} -E make_directory ${INSTCTXT_dest_dir}
		COMMAND rez-config --print-env --no-path-append --wrapper --mode=${mode} --meta-info=tools --meta-info-shallow=tools --dot-file=${INSTCTXT_dest_dir}/${target}.dot ${INSTCTXT_PACKAGES} >> ${INSTCTXT_dest_dir}/${target}
		COMMAND echo "export REZ_CONTEXT_FILE=$REZ_${uproj}_ROOT/${INSTCTXT_dest_dir}/${target}" >> ${INSTCTXT_dest_dir}/${target}
		COMMAND echo "${INSTCTXT_EXTRA_COMMANDS2}" >> ${INSTCTXT_dest_dir}/${target}
		COMMAND echo "export PATH=$PATH:/bin:/usr/bin" >> ${INSTCTXT_dest_dir}/${target}
		COMMENT "Building context file ${INSTCTXT_dest_dir}/${target} for package request: ${INSTCTXT_PACKAGES2}"
		VERBATIM
	)

	install(
		FILES ${CMAKE_CURRENT_BINARY_DIR}/${INSTCTXT_dest_dir}/${target}
		DESTINATION ${INSTCTXT_dest_dir}
		PERMISSIONS ${REZ_FILE_INSTALL_PERMISSIONS} )

	install(
		FILES ${CMAKE_CURRENT_BINARY_DIR}/${INSTCTXT_dest_dir}/${target}.dot
		DESTINATION ${INSTCTXT_dest_dir}
		PERMISSIONS ${REZ_FILE_INSTALL_PERMISSIONS} )

	add_custom_target ( ${label} ALL DEPENDS
		${CMAKE_CURRENT_BINARY_DIR}/${INSTCTXT_dest_dir}/${target}
		${CMAKE_CURRENT_BINARY_DIR}/${INSTCTXT_dest_dir}/${target}.dot
	)

endmacro (rez_install_context)
