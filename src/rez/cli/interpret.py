# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


'''
Execute some Rex code and print the interpreted result.
'''
from __future__ import print_function


def setup_parser(parser, completions=False):
    from rez.shells import get_shell_types
    from rez.system import system

    formats = get_shell_types() + ['dict', 'table']

    parser.add_argument(
        "-f", "--format", type=str, choices=formats,
        help="print output in the given format. If None, the current shell "
        "language (%s) is used" % system.shell)
    parser.add_argument(
        "--no-env", dest="no_env", action="store_true",
        help="interpret the code in an empty environment")
    pv_action = parser.add_argument(
        "--pv", "--parent-variables", dest="parent_vars", type=str,
        metavar='VAR', nargs='+',
        help="environment variables to update rather than overwrite on first "
        "reference. If this is set to the special value 'all', all variables "
        "will be treated this way")
    FILE_action = parser.add_argument(
        "FILE", type=str,
        help='file containing rex code to execute')

    if completions:
        from rez.cli._complete_util import FilesCompleter
        from rez.vendor.argcomplete.completers import EnvironCompleter
        pv_action.completer = EnvironCompleter
        FILE_action.completer = FilesCompleter(dirs=False,
                                               file_patterns=["*.py", "*.rex"])


def command(opts, parser, extra_arg_groups=None):
    from rez.shells import create_shell
    from rez.utils.formatting import columnise
    from rez.rex import RexExecutor, Python
    from pprint import pformat

    with open(opts.FILE) as f:
        code = f.read()

    interp = None
    if opts.format is None:
        interp = create_shell()
    elif opts.format in ('dict', 'table'):
        interp = Python(passive=True)
    else:
        interp = create_shell(opts.format)

    parent_env = {} if opts.no_env else None

    if opts.parent_vars == "all":
        parent_vars = True
    else:
        parent_vars = opts.parent_vars

    ex = RexExecutor(interpreter=interp,
                     parent_environ=parent_env,
                     parent_variables=parent_vars)

    ex.execute_code(code, filename=opts.FILE)

    o = ex.get_output()
    if isinstance(o, dict):
        if opts.format == "table":
            rows = [x for x in sorted(o.items())]
            print('\n'.join(columnise(rows)))
        else:
            print(pformat(o))
    else:
        print(o)
