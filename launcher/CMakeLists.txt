cmake_minimum_required(VERSION 3.15)

project(simple_launcher LANGUAGES C)

add_executable(simple_launcher_cli launcher.c)
target_link_libraries(simple_launcher_cli shlwapi.lib)
target_compile_definitions(simple_launcher_cli PUBLIC -D_CONSOLE)
target_compile_options(simple_launcher_cli PUBLIC /MT)

add_executable(simple_launcher_gui WIN32 launcher.c)
target_link_libraries(simple_launcher_gui shlwapi.lib)
target_compile_options(simple_launcher_gui PUBLIC /MT)
