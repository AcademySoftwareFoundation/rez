name = 'variants_py'

version = "2.0"

description = "package with variants"

requires = ["python-2.7"]

variants = [
    ["platform-linux"],
    ["platform-osx"]
]

def commands():
    env.PATH.append("{root}/bin")
