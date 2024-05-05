# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Entry points.
"""
import os
import os.path
import sys
import json
import dataclasses
import typing


@dataclasses.dataclass
class EntryPoint:
    type: str
    func: str


### Utility functions

def get_specifications() -> typing.Dict[str, EntryPoint]:
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
            specs[scriptname] = EntryPoint(func=attr, type=getattr(obj, "__scripttype__"))
    return specs


def register(name, _type="console"):
    def decorator(fn):
        setattr(fn, "__scriptname__", name)
        setattr(fn, "__scripttype__", _type)
        return fn
    return decorator

### Entry points

@register("rez")
def run_rez():
    from rez.cli._main import run
    return run()


@register("rezolve")
def run_rezolve():
    # alias for osx, where rez is a different tool
    # https://www.unix.com/man-page/osx/1/REZ/
    from rez.cli._main import run
    return run()


@register("_rez-complete")
def run_rez_complete():
    from rez.cli._main import run
    return run("complete")


@register("_rez_fwd")
def run_rez_fwd():
    from rez.cli._main import run
    return run("forward")


@register("rez-bind")
def run_rez_bind():
    from rez.cli._main import run
    return run("bind")


@register("rez-build")
def run_rez_build():
    from rez.cli._main import run
    return run("build")


@register("rez-config")
def run_rez_config():
    from rez.cli._main import run
    return run("config")


@register("rez-context")
def run_rez_context():
    from rez.cli._main import run
    return run("context")


@register("rez-cp")
def run_rez_cp():
    from rez.cli._main import run
    return run("cp")


@register("rez-depends")
def run_rez_depends():
    from rez.cli._main import run
    return run("depends")


@register("rez-diff")
def run_rez_diff():
    from rez.cli._main import run
    return run("diff")


@register("rez-env")
def run_rez_env():
    from rez.cli._main import run
    return run("env")


@register("rez-gui", "window")
def run_rez_gui():
    from rez.cli._main import run
    return run("gui")


@register("rez-help")
def run_rez_help():
    from rez.cli._main import run
    return run("help")


@register("rez-interpret")
def run_rez_interpret():
    from rez.cli._main import run
    return run("interpret")


@register("rez-memcache")
def run_rez_memcache():
    from rez.cli._main import run
    return run("memcache")


@register("rez-pip")
def run_rez_pip():
    from rez.cli._main import run
    return run("pip")


@register("rez-pkg-cache")
def run_rez_pkg_cache():
    from rez.cli._main import run
    return run("pkg-cache")


@register("rez-plugins")
def run_rez_plugins():
    from rez.cli._main import run
    return run("plugins")


@register("rez-python")
def run_rez_python():
    from rez.cli._main import run
    return run("python")


@register("rez-release")
def run_rez_release():
    from rez.cli._main import run
    return run("release")


@register("rez-search")
def run_rez_search():
    from rez.cli._main import run
    return run("search")


@register("rez-selftest")
def run_rez_selftest():
    from rez.cli._main import run
    return run("selftest")


@register("rez-status")
def run_rez_status():
    from rez.cli._main import run
    return run("status")


@register("rez-suite")
def run_rez_suite():
    from rez.cli._main import run
    return run("suite")


@register("rez-test")
def run_rez_test():
    from rez.cli._main import run
    return run("test")


@register("rez-view")
def run_rez_view():
    from rez.cli._main import run
    return run("view")


@register("rez-yaml2py")
def run_rez_yaml2py():
    from rez.cli._main import run
    return run("yaml2py")


@register("rez-bundle")
def run_rez_bundle():
    from rez.cli._main import run
    return run("bundle")


@register("rez-benchmark")
def run_rez_benchmark():

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
    from rez.cli._main import run
    return run("pkg-ignore")


@register("rez-mv")
def run_rez_mv():
    from rez.cli._main import run
    return run("mv")


@register("rez-rm")
def run_rez_rm():
    from rez.cli._main import run
    return run("rm")


@register("_rez-install-test")
def run_rez_install_test():
    data = {
        "argv": sys.argv,
        "executable": sys.executable,
        "sysflags": {
            attr: getattr(sys.flags, attr)
            for attr in dir(sys.flags)
            if not attr.startswith("_") and not callable(getattr(sys.flags, attr))
        }
    }

    print(json.dumps(data, indent=4))
    return 0
