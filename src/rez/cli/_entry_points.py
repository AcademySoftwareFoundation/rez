"""
Entry points.
"""
import os.path
import sys


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
    specs = {}

    for attr, obj in sys.modules[__name__].__dict__.items():
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


def check_production_install():
    path = os.path.dirname(sys.argv[0])
    filepath = os.path.join(path, ".rez_production_install")

    if not os.path.exists(filepath):
        sys.stderr.write(
            "Pip-based rez installation detected. Please be aware that rez command "
            "line tools are not guaranteed to function correctly in this case. See "
            "https://github.com/nerdvegas/rez/wiki/Installation#why-not-pip-for-production "
            " for futher details.\n"
        )


### Entry points

@scriptname("rez")
def run_rez():
    check_production_install()
    from rez.cli._main import run
    return run()


@scriptname("rezolve")
def run_rezolve():
    # alias for osx, where rez is a different tool
    # https://www.unix.com/man-page/osx/1/REZ/
    check_production_install()
    from rez.cli._main import run
    return run()


@scriptname("bez")
def run_bez():
    # TODO: Deprecate. Use custom build commands instead.
    # https://github.com/nerdvegas/rez/wiki/Building-Packages#custom-build-commands
    check_production_install()
    from rez.cli._bez import run
    run()


@scriptname("_rez-complete")
def run_rez_complete():
    check_production_install()
    from rez.cli._main import run
    return run("complete")


@scriptname("_rez_fwd")
def run_rez_fwd():
    check_production_install()
    from rez.cli._main import run
    return run("forward")


@scriptname("rez-bind")
def run_rez_bind():
    check_production_install()
    from rez.cli._main import run
    return run("bind")


@scriptname("rez-build")
def run_rez_build():
    check_production_install()
    from rez.cli._main import run
    return run("build")


@scriptname("rez-config")
def run_rez_config():
    check_production_install()
    from rez.cli._main import run
    return run("config")


@scriptname("rez-context")
def run_rez_context():
    check_production_install()
    from rez.cli._main import run
    return run("context")


@scriptname("rez-cp")
def run_rez_cp():
    check_production_install()
    from rez.cli._main import run
    return run("cp")


@scriptname("rez-depends")
def run_rez_depends():
    check_production_install()
    from rez.cli._main import run
    return run("depends")


@scriptname("rez-diff")
def run_rez_diff():
    check_production_install()
    from rez.cli._main import run
    return run("diff")


@scriptname("rez-env")
def run_rez_env():
    check_production_install()
    from rez.cli._main import run
    return run("env")


@scriptname("rez-gui")
def run_rez_gui():
    check_production_install()
    from rez.cli._main import run
    return run("gui")


@scriptname("rez-help")
def run_rez_help():
    check_production_install()
    from rez.cli._main import run
    return run("help")


@scriptname("rez-interpret")
def run_rez_interpret():
    check_production_install()
    from rez.cli._main import run
    return run("interpret")


@scriptname("rez-memcache")
def run_rez_memcache():
    check_production_install()
    from rez.cli._main import run
    return run("memcache")


@scriptname("rez-pip")
def run_rez_pip():
    check_production_install()
    from rez.cli._main import run
    return run("pip")


@scriptname("rez-plugins")
def run_rez_plugins():
    check_production_install()
    from rez.cli._main import run
    return run("plugins")


@scriptname("rez-python")
def run_rez_python():
    check_production_install()
    from rez.cli._main import run
    return run("python")


@scriptname("rez-release")
def run_rez_release():
    check_production_install()
    from rez.cli._main import run
    return run("release")


@scriptname("rez-search")
def run_rez_search():
    check_production_install()
    from rez.cli._main import run
    return run("search")


@scriptname("rez-selftest")
def run_rez_selftest():
    check_production_install()
    from rez.cli._main import run
    return run("selftest")


@scriptname("rez-status")
def run_rez_status():
    check_production_install()
    from rez.cli._main import run
    return run("status")


@scriptname("rez-suite")
def run_rez_suite():
    check_production_install()
    from rez.cli._main import run
    return run("suite")


@scriptname("rez-test")
def run_rez_test():
    check_production_install()
    from rez.cli._main import run
    return run("test")


@scriptname("rez-view")
def run_rez_view():
    check_production_install()
    from rez.cli._main import run
    return run("view")


@scriptname("rez-yaml2py")
def run_rez_yaml2py():
    check_production_install()
    from rez.cli._main import run
    return run("yaml2py")
