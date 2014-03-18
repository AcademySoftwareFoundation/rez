"""See util.create_forwarding_script()."""
import json


def command(opts, parser=None):
    data = json.loads(opts.JSON)
    if isinstance(data, list):
        if len(data) == 2 and isinstance(data[1], dict):
            nargs = data[0] if isinstance(data[0], list) else [data[0]]
            kwargs = data[1]
        else:
            nargs = data
            kwargs = {}
    else:
        nargs = [data]
        kwargs = {}

    exec("from %s import %s as _target_func_" % (opts.MODULE, opts.FUNC))
    _target_func_(*nargs, **kwargs)
