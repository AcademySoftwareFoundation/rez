name = 'rextest2'
version = '2'

requires = ["rextest-1.3"]

def commands():
    # prepend to existing var
    env.REXTEST_DIRS.append('{root}/data2')
    setenv("REXTEST2_REXTEST_VER", '{resolve.rextest.version}')
    env.REXTEST2_REXTEST_BASE = resolve.rextest.base
