CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(ExternalProject)

rez_find_packages(PREFIX pkgs AUTO)

if (CENTRAL)
    set(rez_path /film/tools/packages/rez/${REZ_VERSION}/CentOS-${CENTOS_VERSION}/python-${PYTHON_MAJOR_VERSION}.${PYTHON_MINOR_VERSION})
else ()
    set(rez_path ${CMAKE_INSTALL_PREFIX})
endif ()

set(python_library_dir ${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_MAJOR_VERSION}.${PYTHON_MINOR_VERSION}/site-packages)


get_filename_component(relative_path_to_setup ${CMAKE_SOURCE_DIR}/setup.py  PATH)
file(RELATIVE_PATH relative_path ${CMAKE_CURRENT_BINARY_DIR} ${relative_path_to_setup})

configure_file(init.csh.in init.csh @ONLY)
configure_file(init.sh.in init.sh @ONLY)
configure_file(setup.py setup.py @ONLY)
configure_file(install.sh install.sh @ONLY)

set(setup_py ${CMAKE_CURRENT_BINARY_DIR}/setup.py)
set(depends ${CMAKE_CURRENT_SOURCE_DIR}/src/rez/__init__.py)
set(output ${CMAKE_CURRENT_BINARY_DIR}/build/lib/rez/__init__.py)

add_custom_command(OUTPUT ${output}
    COMMAND $ENV{PYTHON_EXE} ${setup_py} build
    COMMAND ${CMAKE_COMMAND} -E touch ${output}
    DEPENDS ${depends}
)

add_custom_target(rez ALL DEPENDS ${output})

install(CODE "execute_process(COMMAND ${CMAKE_CURRENT_BINARY_DIR}/install.sh)")
install(FILES ${CMAKE_BINARY_DIR}/init.sh DESTINATION bin)
install(FILES ${CMAKE_BINARY_DIR}/init.csh DESTINATION bin)

