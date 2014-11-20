'''

'''

from rez.colorize import heading, critical, error, warning, info, Printer
from rez.config import config
from rez.exceptions import RezError
from rez.util import columnise
from operator import attrgetter
import os


priority_mapping = {
     50: critical,
     40: error,
     30: warning,
     20: info
}


def setup_parser(parser, completions=False):

    parser.add_argument("--report-issues", action="store_true",
        help="only report paths that contain an issue.")
    ENVVARS_action = parser.add_argument(
        "ENVVARS", type=str, nargs='*',
        help='variables in the environment to test')

    if completions:
        from rez.cli._complete_util import EnvironmentVariableCompleter
        ENVVARS_action.completer = EnvironmentVariableCompleter


def command(opts, parser, extra_arg_groups=None):

    evironment_variables = opts.ENVVARS
    show_all = not opts.report_issues

    lint(variables=evironment_variables, show_all=show_all)


def lint(variables=None, show_all=True):
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
            if not show_all and not issues:
                continue

            tags = '(%s)' % ', '.join(map(str, issues)) if issues else '(ok)'
            cols = sorted(issues, key=attrgetter('priority'), reverse=True)

            rows.append(("  %s" % path, tags))
            colours.append(priority_mapping[cols[0].priority] if cols else info)

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
