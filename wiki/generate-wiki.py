"""
Script to generate wiki content.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
from collections import defaultdict
import errno
from io import open
import os
import re
import subprocess
import shutil
import sys


# py3.7+ only
if sys.version_info[:2] < (3, 7):
    print("update-wiki.py: use python-3.7 or greater", file=sys.stderr)
    sys.exit(1)


THIS_FILE = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)
REZ_SOURCE_DIR = os.getenv("REZ_SOURCE_DIR", os.path.dirname(THIS_DIR))

OUT_DIR = "out"
GITHUB_REPO = "unknown/rez"
GITHUB_BRANCH = "master"
GITHUB_WORKFLOW = "Wiki"


def add_toc(txt):
    """Add github-style ToC to start of md content.
    """
    lines = txt.split('\n')
    toc_lines = []
    mindepth = None

    for line in lines:
        if not line.startswith('#'):
            continue

        parts = line.split()

        hashblock = parts[0]
        if set(hashblock) != set(["#"]):
            continue

        depth = len(hashblock)
        if mindepth is None:
            mindepth = depth
        depth -= mindepth

        toc_lines.append("%s- [%s](#%s)" % (
            ' ' * 4 * depth,
            ' '.join(parts[1:]),
            '-'.join(x.lower() for x in parts[1:])
        ))

    if not toc_lines:
        return txt

    return '\n'.join(toc_lines) + "\n\n" + txt


def creating_configuring_rez_md(txt):
    lines = txt.split('\n')

    start = None
    end = None
    for i, line in enumerate(lines):
        if "__DOC_START__" in line:
            start = i
        elif "__DOC_END__" in line:
            end = i

    lines = lines[start:end + 1]
    assign_regex = re.compile("^([a-z0-9_]+) =")
    settings = {}

    # parse out settings and their comment
    for i, line in enumerate(lines):
        m = assign_regex.match(line)
        if not m:
            continue

        start_defn = i
        end_defn = i
        while lines[end_defn].strip() and not lines[end_defn].startswith('#'):
            end_defn += 1

        defn_lines = lines[start_defn:end_defn]
        defn_lines = [("    " + x) for x in defn_lines]  # turn into code block
        defn = '\n'.join(defn_lines)

        end_comment = i
        while not lines[end_comment].startswith('#'):
            end_comment -= 1

        start_comment = end_comment
        while lines[start_comment].startswith('#'):
            start_comment -= 1
        start_comment += 1

        comments = lines[start_comment:end_comment + 1]
        comments = [x[2:] for x in comments]  # drop leading '# '
        comment = '\n'.join(comments)

        varname = m.groups()[0]
        settings[varname] = (defn, comment)

    # generate md text
    md = []

    for varname, (defn, comment) in sorted(settings.items()):
        md.append("### %s" % varname)
        md.append("")
        md.append(defn)
        md.append("")
        md.append(comment)
        md.append("")

    md = '\n'.join(md)
    return md


def create_contributors_md(src_path):
    # Make sure aliases KEY is fully lowercase to match correctly!
    aliases = {
        "allan.johns": "Allan Johns",
        "allan johns": "Allan Johns",
        "ajohns": "Allan Johns",
        "nerdvegas": "Allan Johns",
        "nerdvegas@gmail.com": "Allan Johns",
        "method": "Allan Johns",
        "rachel johns": "Allan Johns",
        "root": "Allan Johns",
        "(no author)": "Allan Johns",

        "mylene pepe": "Mylene Pepe",
        "michael.morehouse": "Michael Morehouse",
        "phunter.nz": "Philip Hunter",
        "joe yu": "Joseph Yu",
        "j0yu": "Joseph Yu",
        "fpiparo": "Fabio Piparo"
    }
    out = subprocess.check_output(
        ["git", "shortlog", "-sn", "HEAD"],
        encoding="utf-8",
        cwd=src_path,
    )
    contributors = defaultdict(int)
    regex = re.compile(
        r'^\s*(?P<commits>\d+)\s+(?P<author>.+)\s*$',
        flags=re.MULTILINE | re.UNICODE
    )

    for match in regex.finditer(out):
        author = match.group('author')
        author_html = "%s<br>" % aliases.get(author.lower(), author)
        contributors[author_html] += int(match.group('commits'))

    return '\n'.join(
        author_html for author_html, commit_count in
        sorted(contributors.items(), key=lambda x: x[1], reverse=True)
    )


def process_markdown_files():
    pagespath = os.path.join(THIS_DIR, "pages")
    user, repo_name = GITHUB_REPO.split('/')
    processed_files = {}

    src_path = REZ_SOURCE_DIR
    if src_path is None:
        print(
            "Must provide REZ_SOURCE_DIR which points at root of "
            "rez source clone", file=sys.stderr,
        )
        sys.exit(1)

    def apply_replacements(filename, replacements=None):
        srcfile = os.path.join(pagespath, filename)

        with open(srcfile, encoding='utf-8') as f:
            txt = f.read()

        # add standard replacements
        repls = {
            "__GITHUB_REPO__": GITHUB_REPO,
            "__GITHUB_USER__": user,
            "__GITHUB_BRANCH__": GITHUB_BRANCH,
            "__REPO_NAME__": repo_name
        }

        repls.update(replacements or {})

        for src_txt, repl_txt in repls.items():
            txt = txt.replace(src_txt, repl_txt)

        return txt

    # generate Configuring-Rez.md
    filepath = os.path.join(src_path, "src", "rez", "rezconfig.py")
    with open(filepath) as f:
        txt = f.read()

    processed_files["Configuring-Rez.md"] = apply_replacements(
        "Configuring-Rez.md",
        {
            "__REZCONFIG_MD__": creating_configuring_rez_md(txt)
        }
    )

    # generate Credits.md
    md = create_contributors_md(src_path)
    processed_files["Credits.md"] = apply_replacements(
        "Credits.md",
        {
            "__CONTRIBUTORS_MD__": md
        }
    )

    # generate Command-Line-Tools.md
    processed_files["Command-Line-Tools.md"] = apply_replacements(
        "Command-Line-Tools.md",
        {
            "__GENERATED_MD__": create_clitools_markdown(src_path)
        }
    )

    # all other markdown files
    for name in os.listdir(pagespath):
        if name not in processed_files:
            processed_files[name] = apply_replacements(name)

    # iterate over every file, add a ToC, and write it out
    for name, txt in processed_files.items():
        destfile = os.path.join(OUT_DIR, name)
        txt = add_toc(txt)
        with open(destfile, 'w') as out:
            out.write(txt)


def create_clitools_markdown(src_path):
    """Generate the formatted markdown for each rez cli tool.

    Hot-import rez cli library to get parsers.

    Args:
        src_path (str): Full path to the rez source code repository.

    Returns:
        str: Generated markdown text.
    """
    sys.path.insert(0, os.path.join(src_path, "src"))
    try:
        from rez.cli._main import setup_parser
        from rez.cli._util import LazySubParsersAction

        main_parser = setup_parser()
        command_help = []
        parsers = [main_parser]
        for action in main_parser._actions:
            if isinstance(action, LazySubParsersAction):
                parsers += action.choices.values()

        for arg_parser in parsers:
            arg_parser.formatter_class = MarkdownHelpFormatter
            command_help.append(arg_parser.format_help())
    finally:
        sys.path.pop(0)

    return "\n\n\n".join(command_help)


class MarkdownHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):

    def _format_usage(self, usage, actions, groups, prefix):
        """Override to produce markdown title and code block formatting.

        Return:
            str: Markdown title and code block formatted usage.
        """
        prefix_was_none = prefix is None
        if prefix_was_none:
            prefix = "# {self._prog}\n```\n".format(self=self)

        super_format_usage = super(MarkdownHelpFormatter, self)._format_usage
        formatted_usage = super_format_usage(usage, actions, groups, prefix)

        if prefix_was_none:
            # Fix extra spaces calculated from old "usage: rez ..." prompt
            extra_spaces = "{newline:<{count}} ".format(
                newline="\n",
                count=len("usage: {self._prog}".format(self=self))
            )
            formatted_usage = formatted_usage[:-1] + "```\n"
            formatted_usage = formatted_usage.replace(extra_spaces, "\n")

        return formatted_usage

    def remap_heading(self, heading):
        """Remap argparse headings to shorter, markdown formatted headings.

        Args:
            heading (str): Original heading to remap and format.

        Returns:
            str: Remapped and formatted heading, if any.
        """
        if heading == "optional arguments":
            return "\n**Flags**\n"
        elif heading == "positional arguments":
            return "" if self._prog == "rez" else "\n**Arguments**\n"
        else:
            return heading

    def start_section(self, heading):
        """Extend to remap optional/positional arguments headings.

        Args:
            heading (str): Section heading to parse.
        """
        if self.remap_heading(heading) == heading:
            super(MarkdownHelpFormatter, self).start_section(heading)
        else:
            self._indent()
            self._add_item(self.remap_heading, [heading])
            super(MarkdownHelpFormatter, self).start_section(argparse.SUPPRESS)

    def _fill_text(self, text, width, indent):
        """No indent for description, keep subsequent indents.

        Return:
            str: Description but without leading indents.
        """
        super_fill_text = super(MarkdownHelpFormatter, self)._fill_text
        return super_fill_text(text, width, indent).lstrip()

    def _format_action(self, action):
        """Extend to format rez sub commands as table of links.

        Returns:
            str: Formatted help text for an action.
        """
        backup_width = self._width
        if self._prog == "rez" and action.nargs is None:
            self._width = 2000  # Temporary thicc width to avoid wrapping

        try:
            super_format = super(MarkdownHelpFormatter, self)._format_action
            help_text = super_format(action)
        finally:
            self._width = backup_width

        if self._prog == "rez":
            # Sub commands, format them with links
            if action.nargs is None:
                help_text = re.sub(
                    r'^\s+(\S+)(\s+)',
                    r'[\1](#rez-\1)\2| ',
                    help_text
                )

            # Sub commands heading, format as table heading
            elif action.metavar == "COMMAND":
                help_text = re.sub(
                    r'^\s+COMMAND',
                    "`COMMAND` | Description\n----|----",
                    help_text
                )

        return help_text


class UpdateWikiParser(argparse.ArgumentParser):
    def __init__(self, **kwargs):
        super(UpdateWikiParser, self).__init__(**kwargs)

        self.add_argument(
            "--github-repo",
            default=GITHUB_REPO,
            dest="repo",
            help="Url to GitHub repository without leading github.com/"
        )
        self.add_argument(
            "--github-branch",
            default=GITHUB_BRANCH,
            dest="branch",
            help="Name of git branch that is generating the Wiki"
        )
        self.add_argument(
            "--github-workflow",
            default=GITHUB_WORKFLOW,
            dest="workflow",
            help="Name of GitHub workflow that is generating the Wiki"
        )
        self.add_argument(
            "--out",
            default=OUT_DIR,
            dest="dir",
            help="Output dir"
        )


if __name__ == "__main__":
    # Quick check for "git" and throw meaningful error message
    try:
        subprocess.check_call(["git", "--version"])
    except OSError as error:
        if error.errno == errno.ENOENT:
            raise OSError(errno.ENOENT, '"git" needed but not found in PATH')
        raise

    args = UpdateWikiParser().parse_args()
    GITHUB_REPO = args.repo
    GITHUB_BRANCH = args.branch
    GITHUB_WORKFLOW = args.workflow
    OUT_DIR = os.path.abspath(args.dir)

    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)

    shutil.copytree(
        os.path.join(THIS_DIR, 'media'),
        os.path.join(OUT_DIR, 'media'),
    )

    os.chdir(OUT_DIR)
    process_markdown_files()
