name = "python"

version = "2.7.4"

authors = [
    "Guido van Rossum"
]

description = \
    """
    The Python programming language.
    """

variants = [
    ["platform-linux", "arch-x86_64", "os-Ubuntu-12.04", "gcc-4.8.2"]
]

tools = [
    "python"
]

uuid = "repository.python"

def commands():
    env.PATH.append("{root}/bin")

    if building:
        env.PYTHON_INCLUDE_DIR = "{root}/include"

        # only used to see libpythonX.X.a file
        env.LD_LIBRARY_PATH.append("{root}/lib")
