config_version = 0
name = 'foo'
version = '1.1.0'

build_requires = ["nover"]

private_build_requires = ["build_util"]

def commands():
    env.PYTHONPATH.append('{root}/python')
