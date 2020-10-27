"""See util.create_forwarding_script()."""
import argparse
from rez.vendor.six import six

__doc__ = argparse.SUPPRESS


basestring = six.string_types[0]


def setup_parser(parser, completions=False):
    parser.add_argument("YAML", type=str)
    parser.add_argument("ARG", type=str, nargs=argparse.REMAINDER)


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.utils.platform_ import platform_
    from rez.exceptions import RezSystemError
    from rez.vendor import yaml
    from rez.vendor.yaml.error import YAMLError
    from rez.utils import py23
    import os.path

    # we don't usually want warnings printed in a wrapped tool. But in cases
    # where we do (for debugging) we leave a backdoor - setting $REZ_QUIET=0
    # will stop this warning suppression.
    if "REZ_QUIET" not in os.environ:
        config.override("quiet", True)

    yaml_file = os.path.abspath(opts.YAML)

    cli_args = opts.ARG
    for arg_group in (extra_arg_groups or []):
        cli_args.extend(arg_group)

    if platform_.name == "windows" and yaml_file.lower().endswith(".cmd"):
        with open(yaml_file) as f:
            content = "\n".join(f.readlines()[4:])  # strip batch script
    else:
        with open(yaml_file) as f:
            content = f.read()

    try:
        doc = yaml.load(content, Loader=yaml.FullLoader)
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
    func_args = py23.get_function_arg_names(target_func)

    if "_script" in func_args:
        kwargs["_script"] = yaml_file
    if "_cli_args" in func_args:
        kwargs["_cli_args"] = cli_args

    target_func(*nargs, **kwargs)


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
