"""See util.create_forwarding_script()."""
from rez.vendor import argparse

__doc__ = argparse.SUPPRESS


def setup_parser(parser, completions=False):
    parser.add_argument("YAML", type=str)
    parser.add_argument("ARG", type=str, nargs=argparse.REMAINDER)


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.exceptions import RezSystemError
    from rez.vendor import yaml
    from rez.vendor.yaml.error import YAMLError
    import inspect
    import os.path

    # we don't usually want warnings printed in a wrapped tool. But in cases
    # where we do (for debugging) we leave a backdoor - setting $REZ_QUIET=0
    # will stop this warning suppression.
    if "REZ_QUIET" not in os.environ:
        config.override("quiet", True)

    yaml_file = os.path.abspath(opts.YAML)

    cli_args = opts.ARG
    for arg_group in (extra_arg_groups or []):
        cli_args.append("--")
        cli_args.extend(arg_group)

    with open(yaml_file) as f:
        content = f.read()
    try:
        doc = yaml.load(content)
    except YAMLError as e:
        raise RezSystemError("Invalid executable file %s: %s"
                             % (yaml_file, str(e)))

    func_name = doc["func_name"]
    nargs = doc.get("nargs", [])
    kwargs = doc.get("kwargs", {})

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
