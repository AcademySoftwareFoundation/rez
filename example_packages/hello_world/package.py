name = "hello_world"

version = "1.0.0"

authors = [
    "ajohns"
]

description = \
    """
    Python-based hello world example package.
    """

tools = [
    "hello"
]

build_requires = [
    "python3",
]
variants = [
    ['python3-3'],
]
uuid = "examples.hello_world_py"

def commands():
    env.PYTHONPATH.append("{root}/python")
    env.PATH.append("{root}/bin")
