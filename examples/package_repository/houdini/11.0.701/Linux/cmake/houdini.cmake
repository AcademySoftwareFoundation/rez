#
# houdini
#
# Inputs:
# HOUDINI_COMPONENTS	   houdini libs to link against, eg UI, GEO, UT
#
# Outputs:
# houdini_INCLUDE_DIRS     houdini's include directories
# houdini_LIBRARY_DIRS     houdini's library directories
# houdini_LIBRARIES		   houdini's libraries, NOTE: only if components are chosen
# houdini_DEFINITIONS	   houdini's cflags
#


## Obtain Houdini install location
FIND_PATH( HFS toolkit/include/OP/OP_API.h
  "$ENV{HFS}"
  DOC "Root directory of Houdini"
  )

IF(NOT HFS)
	MESSAGE( FATAL_ERROR "Houdini not found (env-var HFS not defined)." )
ENDIF(NOT HFS)


if(HOUDINI_COMPONENTS)
	set(comps ${HOUDINI_COMPONENTS})
	separate_arguments(comps)
	foreach(comp ${comps})
		find_path(HOUDINI_COMPONENT_${comp} dsolib/libHoudini${comp}.so ${HFS})
		if(HOUDINI_COMPONENT_${comp})
			list(APPEND houdini_LIBRARIES Houdini${comp})
		else(HOUDINI_COMPONENT_${comp})
			message(FATAL_ERROR "Houdini component '${comp}' was NOT found in: ${HFS}.")
		endif(HOUDINI_COMPONENT_${comp})
	endforeach(comp ${comps})
endif(HOUDINI_COMPONENTS)


SET( houdini_INCLUDE_DIRS "${HFS}/toolkit/include" )

IF ( APPLE )
	SET( houdini_LIBRARY_DIRS "${HFS}/../Houdini.app/Contents/MacOS" )
ELSEIF ( WIN32 )
	# Win32
	SET( houdini_LIBRARY_DIRS "${HFS}/custom/houdini/dsolib" )
ELSE ( APPLE )
	# Linux
	SET( houdini_LIBRARY_DIRS "${HFS}/dsolib" )
	SET( HOUDINI_PYTHON_LIBRARY_DIR "${HFS}/python/lib" )
	list(APPEND houdini_LIBRARY_DIRS ${HOUDINI_PYTHON_LIBRARY_DIR} )
ENDIF ( APPLE )

# Common definitions
list(APPEND houdini_DEFINITIONS -DVERSION="$ENV{DRD_HOUDINI_VERSION}")
list(APPEND houdini_DEFINITIONS -DMAKING_DSO )
list(APPEND houdini_DEFINITIONS -DUT_DSO_TAGINFO="DrD" )
list(APPEND houdini_DEFINITIONS -DNEED_SPECIALIZATION_STORAGE )

# Platform-specific definitions
IF ( APPLE )
    # OSX
ELSEIF ( WIN32 )
    # Win32
    list(APPEND houdini_DEFINITIONS -DI386)
    list(APPEND houdini_DEFINITIONS -DWIN32)
    list(APPEND houdini_DEFINITIONS -DSWAP_BITFIELDS)
    list(APPEND houdini_DEFINITIONS -DDLLEXPORT=__declspec\(dllexport\) )
    list(APPEND houdini_DEFINITIONS -DSESI_LITTLE_ENDIAN)
ELSE ( APPLE )
    # Linux common
    list(APPEND houdini_DEFINITIONS -D_GNU_SOURCE)
    list(APPEND houdini_DEFINITIONS -DDLLEXPORT= )
    list(APPEND houdini_DEFINITIONS -DSESI_LITTLE_ENDIAN)
    list(APPEND houdini_DEFINITIONS -DENABLE_THREADS)
    list(APPEND houdini_DEFINITIONS -DUSE_PTHREADS)
    list(APPEND houdini_DEFINITIONS -DENABLE_UI_THREADS)
    list(APPEND houdini_DEFINITIONS -DGCC3)
    list(APPEND houdini_DEFINITIONS -DGCC4)
    list(APPEND houdini_DEFINITIONS -Wno-deprecated)

    # Linux 64 bit
    list(APPEND houdini_DEFINITIONS -DAMD64)
    list(APPEND houdini_DEFINITIONS -DSIZEOF_VOID_P=8)
ENDIF ( APPLE )


##########################################################
# ADD_HOUDINI_PLUGIN
##########################################################

MACRO (ADD_HOUDINI_PLUGIN _lib_NAME)

    ADD_LIBRARY ( ${_lib_NAME} SHARED ${ARGN} )

    IF ( APPLE )
    ELSEIF ( WIN32 )
      TARGET_LINK_LIBRARIES ( ${_lib_NAME}
			${HOUDINI_LIBRARY_DIR}/*.a ${HOUDINI_LIBRARY_DIR}/*.lib)
    ELSE ( APPLE )
    ENDIF ( APPLE )

    SET_TARGET_PROPERTIES ( ${_lib_NAME} PROPERTIES PREFIX "")

ENDMACRO (ADD_HOUDINI_PLUGIN _lib_NAME)


