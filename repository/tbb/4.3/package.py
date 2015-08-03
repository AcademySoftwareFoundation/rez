name = "tbb"

version = "4.3"

authors = [
    "Intel"
]

description = \
    """
    Intel Threading Building Blocks.
    """

build_requires = [
    "gcc-4.8.2"
]

variants = [
    ["platform-linux", "arch-x86_64", "os-Ubuntu-12.04"]
]

uuid = "repository.tbb"

def commands():
    env.LD_LIBRARY_PATH.append("{root}/lib/release")

    if building:
        env.TBB_INCLUDE_DIR = "{root}/include"
