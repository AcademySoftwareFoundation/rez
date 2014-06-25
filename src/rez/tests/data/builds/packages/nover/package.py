config_version = 0
name = 'nover'
version = '1.2.0'
authors = ["joe.bloggs"]
uuid = "156730d7122441e3a5745cc81361f49a"
description = "muy loco"

private_build_requires = ["build_util", "python"]

def commands():
    env.PYTHONPATH.append('{root}/python')
