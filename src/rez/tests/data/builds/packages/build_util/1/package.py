config_version = 0
name = 'build_util'
version = '1'
authors = ["joe.bloggs"]
uuid = "9982b60993af4a4d89e8372472a49d02"
description = "build utilities"

private_build_requires = ["python"]

def commands():
    env.PYTHONPATH.append('{root}/python')
