name = "translate_lib"

version = "2.2.0"

authors = ["axl.rose"]

description = "A simple C++ library with minimal dependencies."

def commands():
    import platform

    env.CMAKE_MODULE_PATH.append("{root}/cmake")

    if platform.system() == "Darwin":
        env.DYLD_LIBRARY_PATH.append("{root}/lib")
    else:
        env.LD_LIBRARY_PATH.append("{root}/lib")

uuid = "38eda6e8-f162-11e0-9de0-0023ae79d988"
