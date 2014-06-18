config_version = 0
name = 'foo'
version = '1.0.0'

build_requires = ["nover"]

private_build_requires = ["build_util", "python"]

def commands():
    env.PYTHONPATH.append('{root}/python')
