# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Entry points.
"""
import os
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
            specs[scriptname] = {"func": attr, "type": getattr(obj, "__scripttype__")}

    return specs


def register(name, _type="console"):
    def decorator(fn):
        setattr(fn, "__scriptname__", name)
        setattr(fn, "__scripttype__", _type)
        return fn
    return decorator


def check_production_install():
    path = os.path.dirname(sys.argv[0])
    filepath = os.path.join(path, ".rez_production_install")

    if not os.path.exists(filepath):
        sys.stderr.write(
            "Pip-based rez installation detected. Please be aware that rez command "
            "line tools are not guaranteed to function correctly in this case. See "
            "https://rez.readthedocs.io/en/stable/installation.html#why-not-pip-for-production "
            " for futher details.\n"
        )


### Entry points

@register("jctest")
def run_jctest():
    print("argv:", sys.argv)
    print("executable:", sys.executable)
    print("sys.flags:", sys.flags)
    return 0


@register("rez")
def run_rez():
    check_production_install()
    from rez.cli._main import run
    return run()


@register("rezolve")
def run_rezolve():
    # alias for osx, where rez is a different tool
    # https://www.unix.com/man-page/osx/1/REZ/
    check_production_install()
    from rez.cli._main import run
    return run()


@register("_rez-complete")
def run_rez_complete():
    check_production_install()
    from rez.cli._main import run
    return run("complete")


@register("_rez_fwd")
def run_rez_fwd():
    check_production_install()
    from rez.cli._main import run
    return run("forward")


@register("rez-bind")
def run_rez_bind():
    check_production_install()
    from rez.cli._main import run
    return run("bind")


@register("rez-build")
def run_rez_build():
    check_production_install()
    from rez.cli._main import run
    return run("build")


@register("rez-config")
def run_rez_config():
    check_production_install()
    from rez.cli._main import run
    return run("config")


@register("rez-context")
def run_rez_context():
    check_production_install()
    from rez.cli._main import run
    return run("context")


@register("rez-cp")
def run_rez_cp():
    check_production_install()
    from rez.cli._main import run
    return run("cp")


@register("rez-depends")
def run_rez_depends():
    check_production_install()
    from rez.cli._main import run
    return run("depends")


@register("rez-diff")
def run_rez_diff():
    check_production_install()
    from rez.cli._main import run
    return run("diff")


@register("rez-env")
def run_rez_env():
    check_production_install()
    from rez.cli._main import run
    return run("env")


@register("rez-gui", "window")
def run_rez_gui():
    check_production_install()
    from rez.cli._main import run
    return run("gui")


@register("rez-help")
def run_rez_help():
    check_production_install()
    from rez.cli._main import run
    return run("help")


@register("rez-interpret")
def run_rez_interpret():
    check_production_install()
    from rez.cli._main import run
    return run("interpret")


@register("rez-memcache")
def run_rez_memcache():
    check_production_install()
    from rez.cli._main import run
    return run("memcache")


@register("rez-pip")
def run_rez_pip():
    check_production_install()
    from rez.cli._main import run
    return run("pip")


@register("rez-pkg-cache")
def run_rez_pkg_cache():
    check_production_install()
    from rez.cli._main import run
    return run("pkg-cache")


@register("rez-plugins")
def run_rez_plugins():
    check_production_install()
    from rez.cli._main import run
    return run("plugins")


@register("rez-python")
def run_rez_python():
    check_production_install()
    from rez.cli._main import run
    return run("python")


@register("rez-release")
def run_rez_release():
    check_production_install()
    from rez.cli._main import run
    return run("release")


@register("rez-search")
def run_rez_search():
    check_production_install()
    from rez.cli._main import run
    return run("search")


@register("rez-selftest")
def run_rez_selftest():
    check_production_install()
    from rez.cli._main import run
    return run("selftest")


@register("rez-status")
def run_rez_status():
    check_production_install()
    from rez.cli._main import run
    return run("status")


@register("rez-suite")
def run_rez_suite():
    check_production_install()
    from rez.cli._main import run
    return run("suite")


@register("rez-test")
def run_rez_test():
    check_production_install()
    from rez.cli._main import run
    return run("test")


@register("rez-view")
def run_rez_view():
    check_production_install()
    from rez.cli._main import run
    return run("view")


@register("rez-yaml2py")
def run_rez_yaml2py():
    check_production_install()
    from rez.cli._main import run
    return run("yaml2py")


@register("rez-bundle")
def run_rez_bundle():
    check_production_install()
    from rez.cli._main import run
    return run("bundle")


@register("rez-benchmark")
def run_rez_benchmark():
    check_production_install()

    # Special case - we have to override config settings here, before rez is
    # loaded. TODO this would be cleaner if we had an Application object, see #1043
    #
    # /start
    import json

    settings = {
        "memcached_uri": [],
        "package_filter": [],
        "package_orderers": [],
        "allow_unversioned_packages": False,
        "resource_caching_maxsize": -1,
        "cache_packages_path": None
    }

    for setting, value in settings.items():
        os.environ.pop("REZ_" + setting.upper(), None)
        os.environ["REZ_" + setting.upper() + "_JSON"] = json.dumps(value)
    # /end

    from rez.cli._main import run
    return run("benchmark")


@register("rez-pkg-ignore")
def run_rez_pkg_ignore():
    check_production_install()
    from rez.cli._main import run
    return run("pkg-ignore")


@register("rez-mv")
def run_rez_mv():
    check_production_install()
    from rez.cli._main import run
    return run("mv")


@register("rez-rm")
def run_rez_rm():
    check_production_install()
    from rez.cli._main import run
    return run("rm")
