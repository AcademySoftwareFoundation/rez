"""
Environment variable and alias lookup.
"""


from rez.rex import RexExecutor, Alias, Appendenv, Prependenv, Resetenv, Setenv, Unsetenv
from rez.colorize import heading, Printer
from rez.config import config
from rez.packages import iter_packages, iter_package_families
from rez.vendor.version import version
from rez.util import ProgressBar
import os.path


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path.")
    parser.add_argument(
        "VAR", type=str,
        help="environment variable or alias to search for.")


class WhatProvidesRexExecutor(RexExecutor):

    def expand(self, value):
        return value


class Provider(object):

    def __init__(self, name, search_path):

        self.name = name
        self.search_path = search_path
        self.actions = {}


def command(opts, parser, extra_arg_groups=None):

    config.override("warn_none", True)
    _pr = Printer()
    providers = []
    search_variable = opts.VAR

    pkg_paths = None
    if opts.paths:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    families = list(iter_package_families(pkg_paths))
    progress_bar = ProgressBar("Searching", len(families))

    def add_provider(package, action):
        name = package.name
        range_ = version.VersionRange.from_version(package.version)
        search_path = package.search_path

        for provider in providers:
            if provider.name == name and provider.search_path == search_path:
                for provider_action in provider.actions:
                    if provider_action == action:
                        provider.actions[provider_action].union(range_)
                        break
        else:
            provider = Provider(name, search_path)
            provider.actions[action] = range_
            providers.append(provider)

    for family in families:
        progress_bar.next()
        for package in iter_packages(name=family.name, paths=pkg_paths):
            if not package.commands:
                continue

            executor = WhatProvidesRexExecutor()
            executor.execute_code(package.commands)

            for action in executor.actions:
                if isinstance(action, (Appendenv, Prependenv, Resetenv, Setenv, Unsetenv)):
                    if action.key == search_variable:
                        add_provider(package, action)

                elif isinstance(action, (Alias, )):
                    if action.args[0] == search_variable:
                        add_provider(package, action)

    progress_bar.finish()

    if not providers:
        _pr("Can not find any package that provides '%s'" % search_variable)
        return 0

    for provider in providers:
        _pr("%s@%s:" % (provider.name, provider.search_path), heading)
        for action, range_ in provider.actions.items():
            _pr("    %s" % range_)
            _pr("        %s" % action)
