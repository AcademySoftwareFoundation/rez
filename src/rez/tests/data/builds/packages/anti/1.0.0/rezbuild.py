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
        print 'Intentionally raising an ImportError since loco should not be available'
        pass



