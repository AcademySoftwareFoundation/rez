name = "boost"

version = "1.55.0"

authors = [
    "boost.org"
]

description = \
    """
    Peer-reviewed portable C++ source libraries.
    """

build_requires = [
    "gcc-4.8.2"
]

variants = [
    ["platform-linux", "arch-x86_64", "os-Ubuntu-12.04", "python-2.7"]
]

uuid = "repository.boost"

def commands():
    if building:
        env.BOOST_INCLUDE_DIR = "{root}/include"

        # static libs
        env.LD_LIBRARY_PATH.append("{root}/lib")
