"""See util.create_forwarding_script()."""
import sys
import os.path
from rez.vendor import argparse

__doc__ = argparse.SUPPRESS


def setup_parser(parser):
    parser.add_argument("YAML", type=str)
    parser.add_argument("ARG", type=str, nargs=argparse.REMAINDER)

def command(opts):
    from rez.vendor import yaml
    import importlib
    import inspect

    yaml_file = os.path.abspath(opts.YAML)
    cli_args = opts.ARG

    with open(yaml_file) as f:
        doc = yaml.load(f.read())

    namespace = "rez.%s" % doc["module"]
    func_name = doc["func_name"]
    nargs = doc.get("nargs", [])
    kwargs = doc.get("kwargs", {})

    module = importlib.import_module(namespace)

    target_func = getattr(module, func_name)
    func_args = inspect.getargspec(target_func).args
    if "_script" in func_args:
        kwargs["_script"] = yaml_file
    if "_cli_args" in func_args:
        kwargs["_cli_args"] = cli_args

    target_func(*nargs, **kwargs)
