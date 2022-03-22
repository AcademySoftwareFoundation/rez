from __future__ import print_function
import os

from build_util import build_directory_recurse, check_visible



def build(source_path, build_path, install_path, targets):

    # normal requirement 'foo' should be visible
    check_visible("bah", "foo")
    import foo
    print(foo.report())

    # 'floob' should be visible - it is a build requirement of foo, and
    # build requirements are transitive
    check_visible("bah", "floob")
    import floob
    print(floob.hello())

    # do the build
    if "install" not in (targets or []):
        install_path = None

    build_directory_recurse(src_dir="bah",
                            dest_dir=os.path.join("python", "bah"),
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
