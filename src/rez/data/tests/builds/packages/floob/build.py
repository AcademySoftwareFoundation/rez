from build_util import build_directory_recurse
import os.path


def build(source_path, build_path, install_path, targets):

    if "install" not in (targets or []):
        install_path = None

    build_directory_recurse(src_dir="floob",
                            dest_dir=os.path.join("python", "floob"),
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
