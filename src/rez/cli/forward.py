import argparse
__doc__ = argparse.SUPPRESS

# See util.create_forwarding_script().

import sys
import os.path

def setup_parser(parser):
    parser.add_argument("YAML", type=str)
    parser.add_argument("ARG", type=str, nargs=argparse.REMAINDER)

def command(opts):
    import yaml
    import inspect

    args = sys.argv
    assert(len(args) >= 3)
    assert(os.path.basename(args[0]) == "rezolve")
    assert(args[1] == "forward")
    assert(args[2] == opts.YAML)

    yaml_file = os.path.abspath(opts.YAML)
    cli_args = args[3:]

    with open(yaml_file) as f:
        doc = yaml.load(f.read())

    module = "rez.%s" % doc["module"]
    func_name = doc["func_name"]
    nargs = doc.get("nargs", [])
    kwargs = doc.get("kwargs", {})

    module = __import__(module, globals(), locals(), [], -1)
    target_func = getattr(module, func_name)
    func_args = inspect.getargspec(target_func).args
    if "_script" in func_args:
        kwargs["_script"] = yaml_file
    if "_cli_args" in func_args:
        kwargs["_cli_args"] = cli_args

    target_func(*nargs, **kwargs)
