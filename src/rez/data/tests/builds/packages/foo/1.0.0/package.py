name = 'foo'
version = '1.0.0'
authors = ["joe.bloggs"]
uuid = "8031b8a1b1994ea8af86376647fbe530"
description = "foo thing"

build_requires = ["floob"]

private_build_requires = ["build_util", "python"]

def pre_build_commands() -> None:
    env.FOO_TEST_VAR = "hello"

def commands() -> None:
    env.PYTHONPATH.append('{root}/python')

build_command = 'python {root}/build.py {install}'
