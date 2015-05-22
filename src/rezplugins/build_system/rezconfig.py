import os


cmake = {
    # The name of the CMake build system to use, valid options are
    # eclipse, make, nmake, xcode and codeblocks.
    "build_system": "make",

    # The name of the CMake build target to use, valid options are Debug,
    # Release and RelWithDebInfo.
    "build_target": "Release",

    # A list of default arguments to be passed to the cmake binary.
    "cmake_args" : [
        '-DCMAKE_SKIP_RPATH=1',
    ],

    # Optionally specify an explicit cmake executable to use for building.
    "cmake_binary": None,

    # Optionally specify an explicit make executable to use for building.
    "make_binary": None,

    # If True, install pyc files when the 'rez_install_python' macro is used.
    "install_pyc": True,
}

if os.name != "posix":
    cmake["build_system"] = "nmake"
    cmake["make_binary"] = "nmake"
