config_version = 0
name = 'build_util'
version = '1'

private_build_requires = ["python"]

def commands():
    env.PYTHONPATH.append('{root}/python')
