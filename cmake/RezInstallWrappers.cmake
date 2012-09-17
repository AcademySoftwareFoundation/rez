#
# rez_install_wrappers
#
# This macro installs a context, and also generates a set of wrapper scripts that will
# source this context. For example, say you create a context which contains houdini,
# and you know that the 'hescape' binary is visible on $PATH in this context. If you
# create a wrapper for 'hescape', then a 'hescape' wrapper script will be generated,
# which sources the context and then invokes 'hescape'.
#
# 'label': just a name for the target which builds the context file.
#
# 'context_target': name of the context file to generate.
#
# 'context_name': a name for the context associated with the wrapper. You may have
# multiple wrappers which boot into the same context, and when you start an interactive
# shell within that context with the ---i option, 'context_name' is the label which
# will be written into the prompt.
#
# MODE: resolution mode [default: latest]
#
# PACKAGES: packages in the context.
#
# WRAPPERS: wrapper scripts to generate. If a wrapper name is provided of the form
# "FOO:BAH", then the wrapper can be given a different name to the command it will
# invoke - in this example, the wrapper is called FOO and will invoke BAH.
#
# DESTINATION: relative directory where wrappers and context will be installed to.
#
# EXTRA_COMMANDS: extra bash commands, will be added to the end of the context
#
# Usage:
# rez_install_context(<label> <context_target> <context_name>
#	[MODE earliest|latest]
#	PACKAGES pkg1 pkg2 ... pkgN
#	WRAPPERS wrap1 wrap2 ... wrapN
#	DESTINATION <target_dir>
#	[EXTRA_COMMANDS cmd1 cmd2 ... cmdN] )
#
# Eg:
# rez_install_wrappers(
#	foowrapper
#	foo.context
#	foo
#	MODE latest
#	PACKAGES houdini-11
# 	WRAPPERS hou:hescape
#	DESTINATION .
# )
#

include(Utils)
include(RezInstallContext)


macro (rez_install_wrappers)

	#
	# parse args
	#

	parse_arguments(INSTWRP "MODE;PACKAGES;WRAPPERS;DESTINATION;EXTRA_COMMANDS" "" ${ARGN})

	list(GET INSTWRP_DEFAULT_ARGS 0 instwrp_label)
	if(NOT instwrp_label)
		message(FATAL_ERROR "need to specify a label in call to rez_install_wrappers")
	endif(NOT instwrp_label)

	list(GET INSTWRP_DEFAULT_ARGS 1 instwrp_context_target)
	if(NOT instwrp_context_target)
		message(FATAL_ERROR "need to specify a context target in call to rez_install_wrappers")
	endif(NOT instwrp_context_target)

	list(GET INSTWRP_DEFAULT_ARGS 2 instwrp_context_name)
	if(NOT instwrp_context_name)
		message(FATAL_ERROR "need to specify a context name in call to rez_install_wrappers")
	endif(NOT instwrp_context_name)

	if(NOT INSTWRP_WRAPPERS)
		message(FATAL_ERROR "no wrappers listed in call to rez_install_wrappers")
	endif(NOT INSTWRP_WRAPPERS)

	list(GET INSTWRP_DESTINATION 0 INSTWRP_dest_dir)
	if(NOT INSTWRP_dest_dir)
		message(FATAL_ERROR "need to specify DESTINATION in call to rez_install_wrappers")
	endif(NOT INSTWRP_dest_dir)


	#
	# build and install context
	#

	set(instctxt_label ${instwrp_label}-context)

	rez_install_context(
		${instctxt_label} ${ARGV1}
		MODE ${INSTWRP_MODE}
		PACKAGES ${INSTWRP_PACKAGES}
		DESTINATION ${INSTWRP_DESTINATION}
		EXTRA_COMMANDS ${INSTWRP_EXTRA_COMMANDS}
	)


	#
	# build and install wrapper scripts
	#

	foreach(wrapper ${INSTWRP_WRAPPERS})

		set(wrapper_script ${wrapper})
		set(alias ${wrapper})

		# separate out 'wrapper_script:alias' if this form is being used
		string(REPLACE ":" ";" wrapper2 ${wrapper})
		list(LENGTH wrapper2 wlen)
		if(wlen EQUAL 2)
			list(GET wrapper2 0 wrapper_script)
			list(GET wrapper2 1 alias)
		endif(wlen EQUAL 2)

		add_custom_command(
			OUTPUT ${INSTWRP_dest_dir}/${wrapper_script}
			COMMAND ${CMAKE_COMMAND} -E make_directory ${INSTWRP_dest_dir}
			COMMAND cat $ENV{REZ_PATH}/template/wrapper.sh | sed -e "s/#CONTEXT#/${instwrp_context_target}/g" -e "s/#CONTEXTNAME#/${instwrp_context_name}/g" -e "s/#ALIAS#/${alias}/g" -e "s/#RCFILE#//g" > ${INSTWRP_dest_dir}/${wrapper_script}
			COMMENT "Building wrapper script ${INSTWRP_dest_dir}/${wrapper_script}"
			VERBATIM
		)

		install(
			FILES ${CMAKE_CURRENT_BINARY_DIR}/${INSTWRP_dest_dir}/${wrapper_script}
			DESTINATION ${INSTWRP_dest_dir}
			PERMISSIONS ${REZ_EXECUTABLE_FILE_INSTALL_PERMISSIONS}
		)

		list(APPEND wrappers ${CMAKE_CURRENT_BINARY_DIR}/${INSTWRP_dest_dir}/${wrapper_script})

	endforeach(wrapper ${INSTWRP_WRAPPERS})

	add_custom_target ( ${instwrp_label} ALL DEPENDS ${wrappers} )

endmacro (rez_install_wrappers)




















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
