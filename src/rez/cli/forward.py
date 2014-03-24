"""See util.create_forwarding_script()."""
import yaml
import sys
import inspect
import os.path


def command(opts, parser=None):
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

    exec("from %s import %s as _target_func_" % (module, func_name))
    func_args = inspect.getargspec(_target_func_).args
    if "_script" in func_args:
        kwargs["_script"] = yaml_file
    if "_cli_args" in func_args:
        kwargs["_cli_args"] = cli_args

    _target_func_(*nargs, **kwargs)
