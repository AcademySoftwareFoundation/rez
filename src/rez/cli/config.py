# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


'''
Print current rez settings.
'''
from __future__ import print_function

import json


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--json", dest="json", action="store_true",
        help="Output dict/list field values as JSON. Useful for setting "
             "REZ_*_JSON environment variables. Ignored if FIELD not given")
    parser.add_argument(
        "--search-list", dest="search_list", action="store_true",
        help="list the config files searched")
    parser.add_argument(
        "--source-list", dest="source_list", action="store_true",
        help="list the config files sourced")
    FIELD_action = parser.add_argument(
        "FIELD", type=str, nargs='?',
        help="print the value of a specific setting")

    if completions:
        from rez.cli._complete_util import ConfigCompleter
        FIELD_action.completer = ConfigCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.config import config
    from rez.utils.yaml import dump_yaml
    from rez.utils.data_utils import convert_json_safe

    if opts.search_list:
        for filepath in config.filepaths:
            print(filepath)
        return

    if opts.source_list:
        for filepath in config.sourced_filepaths:
            print(filepath)
        return

    data = config.data
    if opts.FIELD:
        keys = opts.FIELD.split('.')
        while keys:
            key = keys[0]
            keys = keys[1:]
            try:
                data = data[key]
            except KeyError:
                raise ValueError("no such setting: %r" % opts.FIELD)

    if isinstance(data, (dict, list)):
        if opts.json:
            txt = json.dumps(convert_json_safe(data))
        else:
            txt = dump_yaml(data)

        print(txt.strip())
    else:
        print(data)
