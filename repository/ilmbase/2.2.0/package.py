name = "ilmbase"

version = "2.2.0"

authors = [
    "ILM"
]

description = \
    """
    Utility libraries from ILM used by OpenEXR.
    """

build_requires = [
    "gcc-4.8.2"
]

variants = [
    ["platform-linux", "arch-x86_64", "os-Ubuntu-12.04"]
]

uuid = "repository.ilmbase"

def commands():
    if building:
        env.PKG_CONFIG_PATH.append("{root}/lib/pkgconfig")
        env.ILMBASE_INCLUDE_DIR = "{root}/include"

        # static libs only, hence build-time only
        env.LD_LIBRARY_PATH.append("{root}/lib")
