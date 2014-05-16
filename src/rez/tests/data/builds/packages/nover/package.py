config_version = 0
name = 'nover'

private_build_requires = ["build_util"]

def commands():
    env.PYTHONPATH.append('{root}/python')
