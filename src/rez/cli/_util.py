from __future__ import print_function

import os
import sys
import signal
from argparse import _SubParsersAction, ArgumentParser, SUPPRESS, \
    ArgumentError


# Subcommands and their behaviors.
#
# 'arg_mode' determines how cli args are parsed. Values are:
# * 'grouped': Args can be separated by '--'. This causes args to be grouped into
#   lists which are then passed as 'extra_arg_groups' to each command.
# * 'passthrough': Unknown args are passed as first list in 'extra_arg_groups'.
#   The '--' arg is not treated as a special case.
# * missing: Native python argparse behavior.
#
subcommands = {
    "bind": {},
    "build": {
        "arg_mode": "grouped"
    },
    "config": {},
    "context": {},
    "complete": {
        "hidden": True
    },
    "cp": {},
    "depends": {},
    "diff": {},
    "env": {
        "arg_mode": "grouped"
    },
    "forward": {
        "hidden": True,
        "arg_mode": "passthrough"
    },
    "gui": {},
    "help": {},
    "interpret": {},
    "memcache": {},
    "pip": {},
    "pkg-cache": {},
    "plugins": {},
    "python": {
        "arg_mode": "passthrough"
    },
    "release": {
        "arg_mode": "grouped"
    },
    "search": {},
    "selftest": {
        "arg_mode": "grouped"
    },
    "status": {},
    "suite": {},
    "test": {},
    "view": {},
    "yaml2py": {},
    "bundle": {},
    "benchmark": {},
    "pkg-ignore": {},
    "mv": {},
    "rm": {}
}


def load_plugin_cmd():
    """Load subcommand from command type plugin

    The command type plugin module should have attribute `command_behavior`,
    and the value must be a dict if provided. For example:

        # in your command plugin module
        command_behavior = {
            "hidden": False,   # (bool): default False
            "arg_mode": None,  #  (str): "passthrough", "grouped", default None
        }

    If the attribute not present, default behavior will be given.

    """
    from rez.config import config
    from rez.utils.logging_ import print_debug
    from rez.plugin_managers import plugin_manager

    ext_plugins = dict()

    for plugin_name in plugin_manager.get_plugins("command"):
        module = plugin_manager.get_plugin_module("command", plugin_name)

        behavior = getattr(module, "command_behavior", None)
        if behavior is None:
            behavior = dict()

            if config.debug("plugins"):
                print_debug("Attribute 'command_behavior' not found in plugin "
                            "module %s, registering with default behavior."
                            % module.__name__)
        try:
            data = behavior.copy()
            data.update({"module_name": module.__name__})
            ext_plugins[plugin_name] = data

        except Exception:
            if config.debug("plugins"):
                import traceback
                from rez.vendor.six.six import StringIO
                out = StringIO()
                traceback.print_exc(file=out)
                print_debug(out.getvalue())

    return ext_plugins


subcommands.update(load_plugin_cmd())


class LazySubParsersAction(_SubParsersAction):
    """Argparse Action which calls the `setup_subparser` function provided to
    `LazyArgumentParser`.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        parser_name = values[0]

        # this bit is taken directly from argparse:
        try:
            parser = self._name_parser_map[parser_name]
        except KeyError:
            tup = parser_name, ', '.join(self._name_parser_map)
            msg = 'unknown parser %r (choices: %s)' % tup
            raise ArgumentError(self, msg)

        self._setup_subparser(parser_name, parser)
        caller = super(LazySubParsersAction, self).__call__
        return caller(parser, namespace, values, option_string)

    def _setup_subparser(self, parser_name, parser):
        if hasattr(parser, 'setup_subparser'):
            help_ = parser.setup_subparser(parser_name, parser)
            if help_ is not None:
                if help_ == SUPPRESS:
                    self._choices_actions = [act for act in self._choices_actions
                                             if act.dest != parser_name]
                else:
                    help_action = self._find_choice_action(parser_name)
                    if help_action is not None:
                        help_action.help = help_
            delattr(parser, 'setup_subparser')

    def _find_choice_action(self, parser_name):
        for help_action in self._choices_actions:
            if help_action.dest == parser_name:
                return help_action


class LazyArgumentParser(ArgumentParser):
    """
    ArgumentParser sub-class which accepts an additional `setup_subparser`
    argument for lazy setup of sub-parsers.

    `setup_subparser` is passed 'parser_name', 'parser', and can return a help
    string.
    """
    def __init__(self, *args, **kwargs):
        self.setup_subparser = kwargs.pop('setup_subparser', None)
        super(LazyArgumentParser, self).__init__(*args, **kwargs)
        self.register('action', 'parsers', LazySubParsersAction)

    def format_help(self):
        """Sets up all sub-parsers when help is requested."""
        if self._subparsers:
            for action in self._subparsers._actions:
                if isinstance(action, LazySubParsersAction):
                    for parser_name, parser in action._name_parser_map.items():
                        action._setup_subparser(parser_name, parser)
        return super(LazyArgumentParser, self).format_help()


_handled_int = False
_handled_term = False


def _env_var_true(name):
    return (os.getenv(name, "").lower() in ("1", "true", "on", "yes"))


def print_items(items, stream=sys.stdout):
    try:
        item_per_line = (not stream.isatty())
    except:
        item_per_line = True

    if item_per_line:
        for item in items:
            print(item)
    else:
        print(' '.join(map(str, items)))


def sigbase_handler(signum, frame):
    # show cursor - progress lib may have hidden it
    SHOW_CURSOR = '\x1b[?25h'
    sys.stdout.write(SHOW_CURSOR)
    sys.stdout.flush()

    # kill all child procs
    # FIXME this kills parent procs as well
    if not _env_var_true("_REZ_NO_KILLPG"):
        if os.name == "nt":
            os.kill(os.getpid(), signal.CTRL_C_EVENT)
        else:
            os.killpg(os.getpgid(0), signum)
    sys.exit(1)


def sigint_handler(signum, frame):
    """Exit gracefully on ctrl-C."""
    global _handled_int
    if not _handled_int:
        _handled_int = True
        if not _env_var_true("_REZ_QUIET_ON_SIG"):
            print("Interrupted by user", file=sys.stderr)
        sigbase_handler(signum, frame)


def sigterm_handler(signum, frame):
    """Exit gracefully on terminate."""
    global _handled_term
    if not _handled_term:
        _handled_term = True
        if not _env_var_true("_REZ_QUIET_ON_SIG"):
            print("Terminated by user", file=sys.stderr)
        sigbase_handler(signum, frame)


signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigterm_handler)


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
