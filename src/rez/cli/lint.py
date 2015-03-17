'''
Sanity check envrionment variables in the current environment.  For path based
variables, the following tests are performed:
    * not null - to check an empty string (e.g. '   ') has not been used.
    * duplicate - check for paths that appear more than once.
    * not found - check the path exists on the current system.
    * empty - check the path is not empty.
    * file - the path is a single file (a folder is expected).
'''
from rez.utils.colorize import heading, critical, error, warning, info, Printer
from rez.config import config
from rez.exceptions import RezError
from rez.utils.formatting import columnise
from operator import attrgetter
import os


PRIORITY_MAPPING = {
     50: critical,
     40: error,
     30: warning,
     20: info
}


def setup_parser(parser, completions=False):

    parser.add_argument("--errors-only", action="store_true",
        help="only report paths that contain a problem.")
    ENVVARS_action = parser.add_argument(
        "ENVVARS", type=str, nargs='*',
        help='variables in the environment to test')

    if completions:
        from rez.cli._complete_util import EnvironmentVariableCompleter
        ENVVARS_action.completer = EnvironmentVariableCompleter


def command(opts, parser, extra_arg_groups=None):

    evironment_variables = opts.ENVVARS
    errors_only = opts.errors_only

    lint(variables=evironment_variables, errors_only=errors_only)


def lint(variables=None, errors_only=False):
    if not variables:
        variables = config.lint_variables

    rows = []
    colours = []

    for variable in variables:
        rows.append((variable, ""))
        colours.append(heading)

        results = linter(variable)
        if not results:
            rows.append(("  -- no paths defined --", ""))
            colours.append(info)
            continue

        for path, issues in results:
            if errors_only and not issues:
                continue

            tags = '(%s)' % ', '.join(map(str, issues)) if issues else '(ok)'
            cols = sorted(issues, key=attrgetter('priority'), reverse=True)

            rows.append(("  %s" % path, tags))
            colours.append(PRIORITY_MAPPING[cols[0].priority] if cols else info)

    _pr = Printer()

    for colour, line in zip(colours, columnise(rows)):
        _pr(line, colour)


def linter(variable):
    separator = config.env_var_separators.get(variable, os.pathsep)
    values = os.getenv(variable, "").split(separator)

    consumed = []
    for value in values:
        if not value:
            continue

        issues = []

        for seen in consumed:
            if seen[0] == value:
                issues.append(LintDuplicate())
                break

        else:
            if not value.strip():
                issues.append(LintNull())
            elif not exists(value):
                issues.append(LintNotFound())
            else:
                if is_dir(value):
                    if is_empty(value):
                        issues.append(LintEmpty())
                else:
                    issues.append(LintSingleFile())

        consumed.append((value, issues))

    return consumed


def exists(path):
    return os.path.exists(path)


def is_dir(path):
    return os.path.isdir(path)


def is_empty(path):
    return not bool(os.listdir(path))


class LintError(RezError):
    pass


class LintNull(LintError):
    priority = 30
    colour = warning

    def __str__(self):
        return "null"


class LintDuplicate(LintError):
    priority = 40
    colour = error

    def __str__(self):
        return "duplicate"


class LintNotFound(LintError):
    priority = 50
    colour = critical

    def __str__(self):
        return "not found"


class LintEmpty(LintError):
    priority = 30
    colour = warning

    def __str__(self):
        return "empty"


class LintSingleFile(LintError):
    priority = 20
    colour = info

    def __str__(self):
        return "single file"
