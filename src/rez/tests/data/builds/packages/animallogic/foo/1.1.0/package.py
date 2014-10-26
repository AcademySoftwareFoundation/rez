name = 'foo'
version = '1.1.0'
authors = ["joe.bloggs"]
uuid = "8031b8a1b1994ea8af86376647fbe530"
description = "foo thing"

build_requires = []

private_build_requires = []

def commands():
    env.PYTHONPATH.append('{root}/python')
