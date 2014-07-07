from build_util import check_visible


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

    # note - this package intentionally doesn't build anything
    pass
