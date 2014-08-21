"""See util.create_forwarding_script()."""
import sys
import os.path
from rez.vendor import argparse

__doc__ = argparse.SUPPRESS


def setup_parser(parser, completions=False):
    parser.add_argument("YAML", type=str)
    parser.add_argument("ARG", type=str, nargs=argparse.REMAINDER)


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.vendor import yaml
    import inspect
    import os

    # we don't usually want warnings printed in a wrapped tool. But in cases
    # where we do (for debugging) we leave a backdoor - setting $REZ_QUIET=0
    # will stop this warning suppression.
    if "REZ_QUIET" not in os.environ:
        config.override("quiet", True)

    yaml_file = os.path.abspath(opts.YAML)
    cli_args = opts.ARG

    with open(yaml_file) as f:
        doc = yaml.load(f.read())

    func_name = doc["func_name"]
    nargs = doc.get("nargs", [])
    kwargs = doc.get("kwargs", {})
    plugin_instance = None

    if isinstance(doc["module"], basestring):
        # refers to a rez module
        from rez.backport.importlib import import_module
        namespace = "rez.%s" % doc["module"]
        module = import_module(namespace)
    else:
        # refers to a rez plugin module
        from rez.plugin_managers import plugin_manager
        plugin_type, plugin_name = doc["module"]
        module = plugin_manager.get_plugin_module(plugin_type, plugin_name)

    target_func = getattr(module, func_name)
    func_args = inspect.getargspec(target_func).args
    if "_script" in func_args:
        kwargs["_script"] = yaml_file
    if "_cli_args" in func_args:
        kwargs["_cli_args"] = cli_args

    target_func(*nargs, **kwargs)
