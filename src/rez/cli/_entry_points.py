"""
Entry points.
"""

### Utility functions

def get_specifications():
    """Get entry point specifications

    See:
    * https://pythonhosted.org/distlib/reference.html#distlib.scripts.ScriptMaker.make_multiple
    * https://setuptools.readthedocs.io/en/latest/setuptools.html#automatic-script-creation

    Example return value:

        {
            "rez-env": "rez-env = rez.cli._entry_points.run_rez_env",
            ...
        }

    Returns:
        dict (str, str): The specification string for each script name.
    """
    import sys

    specs = {}

    for attr, obj in sys.modules[__name__].__dict__.iteritems():
        scriptname = getattr(obj, "__scriptname__", None)
        if scriptname:
            spec = "%s = rez.cli._entry_points:%s" % (scriptname, attr)
            specs[scriptname] = spec

    return specs


def scriptname(name):
    def decorator(fn):
        setattr(fn, "__scriptname__", name)
        return fn
    return decorator


### Entry points

@scriptname("rez")
def run_rez():
    from rez.cli._main import run
    return run()


@scriptname("rezolve")
def run_rezolve():
    # alias for osx, where rez is a different tool
    # https://www.unix.com/man-page/osx/1/REZ/
    from rez.cli._main import run
    return run()


@scriptname("bez")
def run_bez():
    # TODO: Deprecate. Use custom build commands instead.
    # https://github.com/nerdvegas/rez/wiki/Building-Packages#custom-build-commands
    from rez.cli._bez import run
    run()


@scriptname("_rez-complete")
def run_rez_complete():
    from rez.cli._main import run
    return run("complete")


@scriptname("_rez-fwd")
def run_rez_fwd():
    from rez.cli._main import run
    return run("forward")


@scriptname("rez-bind")
def run_rez_bind():
    from rez.cli._main import run
    return run("bind")


@scriptname("rez-build")
def run_rez_bind():
    from rez.cli._main import run
    return run("bind")


@scriptname("rez-config")
def run_rez_bind():
    from rez.cli._main import run
    return run("bind")


@scriptname("rez-context")
def run_rez_context():
    from rez.cli._main import run
    return run("context")


@scriptname("rez-cp")
def run_rez_cp():
    from rez.cli._main import run
    return run("cp")


@scriptname("rez-depends")
def run_rez_depends():
    from rez.cli._main import run
    return run("depends")


@scriptname("rez-diff")
def run_rez_diff():
    from rez.cli._main import run
    return run("diff")


@scriptname("rez-env")
def run_rez_env():
    from rez.cli._main import run
    return run("env")


@scriptname("rez-gui")
def run_rez_gui():
    from rez.cli._main import run
    return run("gui")


@scriptname("rez-help")
def run_rez_help():
    from rez.cli._main import run
    return run("help")


@scriptname("rez-interpret")
def run_rez_interpret():
    from rez.cli._main import run
    return run("interpret")


@scriptname("rez-memcache")
def run_rez_memcache():
    from rez.cli._main import run
    return run("memcache")


@scriptname("rez-pip")
def run_rez_pip():
    from rez.cli._main import run
    return run("pip")


@scriptname("rez-plugins")
def run_rez_plugins():
    from rez.cli._main import run
    return run("plugins")


@scriptname("rez-python")
def run_rez_python():
    from rez.cli._main import run
    return run("python")


@scriptname("rez-release")
def run_rez_release():
    from rez.cli._main import run
    return run("release")


@scriptname("rez-search")
def run_rez_search():
    from rez.cli._main import run
    return run("search")


@scriptname("rez-selftest")
def run_rez_selftest():
    from rez.cli._main import run
    return run("selftest")


@scriptname("rez-status")
def run_rez_status():
    from rez.cli._main import run
    return run("status")


@scriptname("rez-suite")
def run_rez_suite():
    from rez.cli._main import run
    return run("suite")


@scriptname("rez-test")
def run_rez_test():
    from rez.cli._main import run
    return run("test")


@scriptname("rez-view")
def run_rez_view():
    from rez.cli._main import run
    return run("view")


@scriptname("rez-yaml2py")
def run_rez_yaml2py():
    from rez.cli._main import run
    return run("yaml2py")
