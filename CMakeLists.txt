CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(ExternalProject)

rez_find_packages(PREFIX pkgs AUTO)

set(rez_path ${CMAKE_INSTALL_PREFIX})

set(python_library_dir ${CMAKE_INSTALL_PREFIX}/lib/python${PYTHON_MAJOR_VERSION}.${PYTHON_MINOR_VERSION}/site-packages)


get_filename_component(relative_path_to_setup ${CMAKE_SOURCE_DIR}/setup.py  PATH)
file(RELATIVE_PATH relative_path ${CMAKE_CURRENT_BINARY_DIR} ${relative_path_to_setup})

get_filename_component(relative_path_to_install ${CMAKE_SOURCE_DIR}/install.py  PATH)

configure_file(init.csh.in init.csh @ONLY)
configure_file(init.sh.in init.sh @ONLY)
configure_file(setup.py setup.py @ONLY)
configure_file(install.py install.py @ONLY)
configure_file(src/rez/_version.py.in ${relative_path_to_install}/src/rez/_version.py @ONLY)

set(install_py ${CMAKE_CURRENT_BINARY_DIR}/install.py)

install(CODE "execute_process(COMMAND $ENV{PYTHON_EXE} ${install_py} -v ${rez_path})")
install(FILES ${CMAKE_BINARY_DIR}/init.sh DESTINATION bin)
install(FILES ${CMAKE_BINARY_DIR}/init.csh DESTINATION bin)
install(FILES ${CMAKE_SOURCE_DIR}/src/rez/completion/_rez_completion
    DESTINATION bin/rez PERMISSIONS OWNER_READ OWNER_EXECUTE GROUP_EXECUTE GROUP_READ WORLD_EXECUTE WORLD_READ )

