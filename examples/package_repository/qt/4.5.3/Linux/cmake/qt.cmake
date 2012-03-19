#
# Input variables:
#
# qt_COMPONENTS: list of components. Use this instead of including qt like so:
# find_package( QT COMPONENTS QtCore QtGui )
#
# All other inputs are identical to the native FindQt4, see:
# http://www.cmake.org/cmake/help/cmake-2-8-docs.html#module:FindQt4
#

if(qt_COMPONENTS)
        find_package(Qt4 4.5.3 COMPONENTS ${qt_COMPONENTS} REQUIRED)
else(qt_COMPONENTS)
        find_package(Qt4 4.5.3 REQUIRED)
endif(qt_COMPONENTS)

if(NOT QT_FOUND)
	message(FATAL_ERROR "Qt find failed.")
endif(NOT QT_FOUND)

include(${QT_USE_FILE})

set(qt_INCLUDE_DIRS ${QT_INCLUDES})
set(qt_LIBRARY_DIRS ${QT_LIBRARY_DIR})
set(qt_LIBRARIES ${QT_LIBRARIES})
set(qt_DEFINITIONS ${QT_DEFINITIONS})

list(APPEND qt_DEFINITIONS -DQT_PLUGIN)
list(APPEND qt_DEFINITIONS -DQT_SHARED)

