name = "hello_lib_meson"

version = "1.1.0"

authors = ["someone else"]

uuid = "70ebae06-ff21-4a59-a387-561c444ad785"

description = "A project that just says hello."

def commands() -> None:
    if system.platform == "osx":
        env.DYLD_LIBRARY_PATH.prepend("{root}/lib")
    else:
        env.LD_LIBRARY_PATH.prepend("{root}/lib")

    if building:
        env.PKG_CONFIG_PATH.prepend("{root}/lib/pkgconfig")
