from build_util import build_directory_recurse, check_visible
import os.path


def build(source_path, build_path, install_path, targets):

    # build requirement 'nover' should be visible
    check_visible("foo", "nover")
    import nover
    print nover.hello()

    # do the build
    if "install" not in (targets or []):
        install_path = None

    build_directory_recurse(src_dir="foo",
                            dest_dir=os.path.join("python", "foo"),
                            source_path=source_path,
                            build_path=build_path,
                            install_path=install_path)
