#
# Input variables:
#
# Boost_COMPONENTS or
# boost_COMPONENTS: list of components. Use this instead of including boost like so:
# find_package( Boost COMPONENTS date_time filesystem system )
#
# All other inputs are identical to the native FindBoost, see:
# http://www.cmake.org/cmake/help/cmake-2-8-docs.html#module:FindBoost
#

set(Boost_DETAILED_FAILURE_MSG 1)

if(boost_STATIC)
	set(Boost_USE_STATIC_LIBS ${boost_STATIC})
endif(boost_STATIC)

if(boost_COMPONENTS)
	set(Boost_COMPONENTS ${boost_COMPONENTS})
endif(boost_COMPONENTS)

if(Boost_COMPONENTS)
	find_package(Boost COMPONENTS ${Boost_COMPONENTS})
else(Boost_COMPONENTS)
	find_package(Boost)
endif(Boost_COMPONENTS)

if(Boost_FOUND)
	set(boost_INCLUDE_DIRS ${Boost_INCLUDE_DIRS})
	set(boost_LIBRARIES ${Boost_LIBRARIES})
	set(boost_LIBRARY_DIRS ${Boost_LIBRARY_DIRS})
else(Boost_FOUND)
	message(FATAL_ERROR "Boost find failed.")
endif(Boost_FOUND)
