from __future__ import print_function

from build_util import build_directory_recurse, check_visible

def build(source_path, build_path, install_path, targets):

    # normal requirement 'foo' should be visible
    check_visible('anti', 'build_util')

    check_visible('anti', 'floob')
    import floob
    floob.hello()

    try:
        import loco
        raise Exception('loco should not be here')
    except ImportError:
        print('Intentionally raising an ImportError since loco should not be available')
        pass


if __name__ == '__main__':
    import os, sys
    build(
        source_path=os.environ['REZ_BUILD_SOURCE_PATH'],
        build_path=os.environ['REZ_BUILD_PATH'],
        install_path=os.environ['REZ_BUILD_INSTALL_PATH'],
        targets=sys.argv[1:]
    )
