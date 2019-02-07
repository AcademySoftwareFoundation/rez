from build_util import build_directory_recurse, check_visible
import os.path


def build(source_path, build_path, install_path, targets):

    # normal requirement 'foo' should be visible
    check_visible("bah", "foo")
    import foo
    print foo.report()

    # 'floob' should be visible - it is a build requirement of foo, and
    # build requirements are transitive
    check_visible("bah", "floob")
    import floob
    print floob.hello()

    # do the build
    if "install" not in (targets or []):
        install_path = None

    build_directory_recurse(src_dir="bah",
                            dest_dir=os.path.join("python", "bah"),
                            source_path=source_path,
                            build_path=build_path,
                            install_path=install_path)


