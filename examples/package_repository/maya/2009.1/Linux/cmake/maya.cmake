#
# Inputs:
#
# maya_COMPONENTS
# list of libraries you want to link to. Defaults to:
# Foundation, OpenMaya
#

set(maya_INCLUDE_DIRS 		$ENV{DRD_MAYA_ROOT}/ext/include)

set(maya_LIBRARY_DIRS        	$ENV{DRD_MAYA_ROOT}/ext/lib)

set(maya_DEFINITIONS         	-D_BOOL -DFUNCPROTO)

if(NOT maya_COMPONENTS)
	set(maya_COMPONENTS	Foundation OpenMaya)
endif(NOT maya_COMPONENTS)

set(comps ${maya_COMPONENTS})
separate_arguments(comps)
foreach(comp ${comps})
	find_path(MAYA_COMPONENT_${comp} lib${comp}.so ${maya_LIBRARY_DIRS})
	if(MAYA_COMPONENT_${comp})
		list(APPEND maya_LIBRARIES ${comp})
	else(MAYA_COMPONENT_${comp})
		find_path(MAYA_STATIC_COMPONENT_${comp} lib${comp}.a ${maya_LIBRARY_DIRS})
		if(MAYA_STATIC_COMPONENT_${comp})
			list(APPEND maya_LIBRARIES ${comp})
		else(MAYA_STATIC_COMPONENT_${comp})
			message(FATAL_ERROR "Maya component '${comp}' was NOT found in: ${maya_LIBRARY_DIRS}.")
		endif(MAYA_STATIC_COMPONENT_${comp})
	endif(MAYA_COMPONENT_${comp})
endforeach(comp ${comps})


##########################################################
# ADD_MAYA_PLUGIN
##########################################################

MACRO (ADD_MAYA_PLUGIN _lib_NAME)

    ADD_LIBRARY ( ${_lib_NAME} SHARED ${ARGN} )
 
ENDMACRO (ADD_MAYA_PLUGIN _lib_NAME)

