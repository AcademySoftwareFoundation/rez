from __future__ import print_function

from build_util import build_directory_recurse, check_visible
import os.path


def build(source_path, build_path, install_path, targets):

    # build requirement 'floob' should be visible
    check_visible("foo", "floob")
    import floob
    print(floob.hello())

    # do the build
    if "install" not in (targets or []):
        install_path = None

    build_directory_recurse(src_dir="foo",
                            dest_dir=os.path.join("python", "foo"),
                            source_path=source_path,
                            build_path=build_path,
                            install_path=install_path)


if __name__ == '__main__':
    import os, sys
    build(
        source_path=os.environ['REZ_BUILD_SOURCE_PATH'],
        build_path=os.environ['REZ_BUILD_PATH'],
        install_path=os.environ['REZ_BUILD_INSTALL_PATH'],
        targets=sys.argv[1:]
    )
