config_version = 0
name = 'rextests'
version = '1.3'

def commands():
    env.REXTEST_ROOT = '{root}'
    env.REXTEST_VERSION = this.version
    env.REXTEST_MAJOR_VERSION = this.version.major
    # prepend to non-existent var
    env.REXTEST_DIRS.prepend('{base}/{version:#.#}/bin')
    alias('rextest', 'foobar')
