name = "gcc"

version = "4.8.2"

authors = [
    "GNU"
]

description = \
    """
    GNU project C and C++ compiler.
    """

variants = [
    ["platform-linux", "arch-x86_64", "os-Ubuntu-12.04"]
]
requires = [ "binutils-2.25" ]

tools = [
    "gcc",
    "g++",
    "c++",
    "cpp",
    "gcc-ar",
    "gcc-ranlib",
    "gfortran",
    "gcc-nm",
    "gcov"
]

uuid = "repository.gcc"

def commands():
    env.PATH.append("{root}/bin")

    if building:
        env.CC = "{root}/bin/gcc"
        env.CXX = "{root}/bin/g++"
