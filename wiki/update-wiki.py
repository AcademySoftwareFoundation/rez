# -*- coding: utf-8 -*-
"""Python implementation of old ``update-wiki.sh`` merged with ``process.py``.

*From ``update-wiki.sh``*

This script calls git heavily to:
1. Takes the content from this repo;
2. Then writes it into a local clone of https://github.com/nerdvegas/rez.wiki.git;
3. Then follows the procedure outlined in README from 2.

This process exists because GitHub does not support contributions to wiki
repositories - this is a workaround.

See Also:
    Original wiki update script files:

    - ``wiki/update-wiki.sh`` at rez 2.50.0, which calls
    - ``utils/process.py`` from nerdvegas/rez.wiki at d632328, and
    - ``utils/update.sh`` from nerdvegas/rez.wiki at d632328
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
from collections import defaultdict
from io import open
import inspect
import os
import re
import subprocess
import shutil
import sys


ORIGINAL_getsourcefile = inspect.getsourcefile
THIS_FILE = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)
REZ_SOURCE_DIR = os.getenv("REZ_SOURCE_DIR", os.path.dirname(THIS_DIR))

TMP_NAME = ".rez-gen-wiki-tmp"  # See also: .gitignore
TEMP_WIKI_DIR = os.getenv("TEMP_WIKI_DIR", os.path.join(THIS_DIR, TMP_NAME))
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "nerdvegas/rez")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "master")
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "Wiki")
CLONE_URL = os.getenv(
    "CLONE_URL",
    "git@github.com:{0}.wiki.git".format(GITHUB_REPO)
)


def PATCHED_getsourcefile(obj):
    """Patch to not return None if path from inspect.getfile is not absolute.

    Returns:
        str: Full path to source code file for an object, else this file path.
    """
    return ORIGINAL_getsourcefile(obj) or THIS_FILE


################################################################################
# https://github.com/rasbt/markdown-toclify
################################################################################

VALIDS = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-&'


def read_lines(in_file):
    """Returns a list of lines from a input markdown file."""

    with open(in_file, 'r') as inf:
        in_contents = inf.read().split('\n')
    return in_contents


def remove_lines(lines, remove=('[[back to top]', '<a class="mk-toclify"')):
    """Removes existing [back to top] links and <a id> tags."""

    if not remove:
        return lines[:]

    out = []
    for l in lines:
        if l.startswith(remove):
            continue
        out.append(l)
    return out


def dashify_headline(line):
    """
    Takes a header line from a Markdown document and
    returns a tuple of the
        '#'-stripped version of the head line,
        a string version for <a id=''></a> anchor tags,
        and the level of the headline as integer.
    E.g.,
    >>> dashify_headline('### some header lvl3')
    ('Some header lvl3', 'some-header-lvl3', 3)
    """
    stripped_right = line.rstrip('#')
    stripped_both = stripped_right.lstrip('#')
    level = len(stripped_right) - len(stripped_both)
    stripped_wspace = stripped_both.strip()

    # character replacements
    replaced_colon = stripped_wspace.replace('.', '')
    replaced_slash = replaced_colon.replace('/', '')
    rem_nonvalids = ''.join([c if c in VALIDS
                             else '-' for c in replaced_slash])

    lowered = rem_nonvalids.lower()
    dashified = re.sub(r'(-)\1+', r'\1', lowered)  # remove duplicate dashes
    dashified = dashified.strip('-')  # strip dashes from start and end

    # exception '&' (double-dash in github)
    dashified = dashified.replace('-&-', '--')

    return [stripped_wspace, dashified, level]


def tag_and_collect(file_lines, id_tag=True, back_links=False, exclude_h=None):
    """
    Gets headlines from the markdown document and creates anchor tags.
    Keyword arguments:
        lines: a list of sublists where every sublist
            represents a line from a Markdown document.
        id_tag: if true, creates inserts a the <a id> tags (not req. by GitHub)
        back_links: if true, adds "back to top" links below each headline
        exclude_h: header levels to exclude. E.g., [2, 3]
            excludes level 2 and 3 headings.
    Returns a tuple of 2 lists:
        1st list:
            A modified version of the input list where
            <a id="some-header"></a> anchor tags where inserted
            above the header lines (if github is False).
        2nd list:
            A list of 3-value sublists, where the first value
            represents the heading, the second value the string
            that was inserted assigned to the IDs in the anchor tags,
            and the third value is an integer that reprents the headline level.
            E.g.,
            [['some header lvl3', 'some-header-lvl3', 3], ...]
    """
    out_contents = []
    headlines = []

    for line in file_lines:
        saw_headline = False
        orig_len = len(line)

        if re.match(r'^\#{1,6} ', line):
            line = line.lstrip()

            # comply with new markdown standards

            # not a headline if '#' not followed by whitespace '##no-header':
            if not line.lstrip('#').startswith(' '):
                continue
            # not a headline if more than 6 '#':
            if len(line) - len(line.lstrip('#')) > 6:
                continue
            # headers can be indented by at most 3 spaces:
            if orig_len - len(line) > 3:
                continue

            # ignore empty headers
            if not set(line) - {'#', ' '}:
                continue

            saw_headline = True
            dashified = dashify_headline(line)

            if not exclude_h or not dashified[-1] in exclude_h:
                if id_tag:
                    id_tag = '<a class="mk-toclify" id="{dashified[1]}"></a>'
                    out_contents.append(id_tag.format(dashified=dashified))
                headlines.append(dashified)

        out_contents.append(line)
        if back_links and saw_headline:
            out_contents.append('[[back to top](#table-of-contents)]')
    return out_contents, headlines


def positioning_headlines(headlines):
    """
    Strips unnecessary whitespaces/tabs if first header is not left-aligned
    """
    left_just = False
    for row in headlines:
        if row[-1] == 1:
            left_just = True
            break
    if not left_just:
        for row in headlines:
            row[-1] -= 1
    return headlines


def create_toc(headlines, hyperlink=True, top_link=False, no_toc_header=False):
    """
    Creates the table of contents from the headline list
    that was returned by the tag_and_collect function.
    Keyword Arguments:
        headlines: list of lists
            e.g., ['Some header lvl3', 'some-header-lvl3', 3]
        hyperlink: Creates hyperlinks in Markdown format if True,
            e.g., '- [Some header lvl1](#some-header-lvl1)'
        top_link: if True, add a id tag for linking the table
            of contents itself (for the back-to-top-links)
        no_toc_header: suppresses TOC header if True.
    Returns  a list of headlines for a table of contents
    in Markdown format,
    e.g., ['        - [Some header lvl3](#some-header-lvl3)', ...]
    """
    processed = []
    if not no_toc_header:
        if top_link:
            processed.append('<a class="mk-toclify" id="table-of-contents"></a>\n')
        processed.append('# Table of Contents')

    for line in headlines:
        indent = (line[2] - 1) * '    '
        if hyperlink:
            item = '%s- [%s](#%s)' % (indent, line[0], line[1])
        else:
            item = '%s- %s' % (indent, line[0])
        processed.append(item)
    processed.append('\n')
    return processed


def build_markdown(toc_headlines, body, spacer=0, placeholder=None):
    """
    Returns a string with the Markdown output contents incl.
    the table of contents.
    Keyword arguments:
        toc_headlines: lines for the table of contents
            as created by the create_toc function.
        body: contents of the Markdown file including
            ID-anchor tags as returned by the
            tag_and_collect function.
        spacer: Adds vertical space after the table
            of contents. Height in pixels.
        placeholder: If a placeholder string is provided, the placeholder
            will be replaced by the TOC instead of inserting the TOC at
            the top of the document
    """
    if spacer:
        spacer_line = ['\n<div style="height:%spx;"></div>\n' % (spacer)]
        toc_markdown = "\n".join(toc_headlines + spacer_line)
    else:
        toc_markdown = "\n".join(toc_headlines)

    body_markdown = "\n".join(body).strip()

    if placeholder:
        markdown = body_markdown.replace(placeholder, toc_markdown)
    else:
        markdown = toc_markdown + body_markdown

    return markdown


def output_markdown(markdown_cont, output_file):
    """
    Writes to an output file if `outfile` is a valid path.
    """
    if output_file:
        with open(output_file, 'w') as out:
            out.write(markdown_cont)


def markdown_toclify(input_file, output_file=None, github=False,
                     back_to_top=False, no_link=False,
                     no_toc_header=False, spacer=0, placeholder=None,
                     exclude_h=None):
    """ Function to add table of contents to markdown files.
    Parameters
    -----------
      input_file: str
        Path to the markdown input file.
      output_file: str (defaul: None)
        Path to the markdown output file.
      github: bool (default: False)
        Uses GitHub TOC syntax if True.
      back_to_top: bool (default: False)
        Inserts back-to-top links below headings if True.
      no_link: bool (default: False)
        Creates the table of contents without internal links if True.
      no_toc_header: bool (default: False)
        Suppresses the Table of Contents header if True
      spacer: int (default: 0)
        Inserts horizontal space (in pixels) after the table of contents.
      placeholder: str (default: None)
        Inserts the TOC at the placeholder string instead
        of inserting the TOC at the top of the document.
      exclude_h: list (default None)
        Excludes header levels, e.g., if [2, 3], ignores header
        levels 2 and 3 in the TOC.
    Returns
    -----------
    cont: str
      Markdown contents including the TOC.
    """
    raw_contents = read_lines(input_file)
    cleaned_contents = remove_lines(raw_contents, remove=('[[back to top]', '<a class="mk-toclify"'))
    processed_contents, raw_headlines = tag_and_collect(
        cleaned_contents,
        id_tag=not github,
        back_links=back_to_top,
        exclude_h=exclude_h,
    )

    leftjustified_headlines = positioning_headlines(raw_headlines)
    processed_headlines = create_toc(leftjustified_headlines,
                                     hyperlink=not no_link,
                                     top_link=not no_link and not github,
                                     no_toc_header=no_toc_header)

    if no_link:
        processed_contents = cleaned_contents

    cont = build_markdown(toc_headlines=processed_headlines,
                          body=processed_contents,
                          spacer=spacer,
                          placeholder=placeholder)

    if output_file:
        output_markdown(cont, output_file)
    return cont


################################################################################
# rez-specific functions
################################################################################

def convert_rezconfig_src_to_md(txt):
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
    out = subprocess.check_output(["git", "shortlog", "-sn", "HEAD"], cwd=src_path)
    out = unicode(out, encoding='utf8')
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
    no_toc = [
        "Credits.md",
        "Command-Line-Tools.md",
        "Home.md",
        "_Footer.md",
        "_Sidebar.md",
    ]

    pagespath = os.path.join(THIS_DIR, "pages")

    src_path = os.getenv("REZ_SOURCE_DIR")
    if src_path is None:
        print(
            "Must provide REZ_SOURCE_DIR which points at root of "
            "rez source clone", file=sys.stderr,
        )
        sys.exit(1)

    def do_replace(filename, token_md):
        srcfile = os.path.join(pagespath, "_%s.md" % filename)
        destfile = os.path.join(TEMP_WIKI_DIR, "%s.md" % filename)

        # with open(srcfile) as f:
        with open(srcfile, encoding='utf-8') as f:
            txt = f.read()

        for token, md in token_md.items():
            txt = txt.replace(token, md)

        print("Writing ", destfile, "...", sep="")
        with open(destfile, 'w', encoding='utf-8') as f:
            f.write(txt)

    # generate markdown from rezconfig.py, add to _Configuring-Rez.md and write
    # out to Configuring-Rez.md
    filepath = os.path.join(src_path, "src", "rez", "rezconfig.py")
    with open(filepath) as f:
        txt = f.read()

    do_replace(
        "Configuring-Rez",
        {
            "__REZCONFIG_MD__": convert_rezconfig_src_to_md(txt),
            "__GITHUB_REPO__": GITHUB_REPO,
        }
    )

    # generate markdown contributors list, add to _Credits.md and write out to
    # Credits.md
    md = create_contributors_md(src_path)
    do_replace("Credits", {"__CONTRIBUTORS_MD__": md})

    do_replace(
        "Command-Line-Tools",
        {
            "__GENERATED_MD__": make_cli_markdown(src_path),
            "__WIKI_PY_URL__": make_cli_source_link(),
        }
    )

    do_replace("_Footer", {"__GITHUB_REPO__": GITHUB_REPO})

    try:
        from urllib import quote
    except ImportError:
        from urllib.parse import quote
    user, repo_name = GITHUB_REPO.split('/')
    do_replace(
        "_Sidebar",
        {
            "__GITHUB_REPO__": GITHUB_REPO,
            "___GITHUB_USER___": user,
            "__REPO_NAME__": repo_name,
            "__WORKFLOW__": quote(GITHUB_WORKFLOW, safe=""),
            "__BRANCH__": quote(GITHUB_BRANCH, safe=""),
        }
    )

    # process each md file:
    # * adds TOC;
    # * replaces short-form content links like '[[here:Blah.md#Header]]' with full form;
    # * copies to the root dir.
    #
    skip_regex = r'^_(?!(Sidebar|Footer))|(?<!.md)$'
    for name in os.listdir(pagespath):
        if re.match(skip_regex, name):
            continue

        print("Processing ", name, "...", sep="")

        src = os.path.join(pagespath, name)
        dest = os.path.join(TEMP_WIKI_DIR, name)

        if name in no_toc:
            shutil.copyfile(src, dest)
            continue

        content = markdown_toclify(input_file=src,
                                   no_toc_header=True,
                                   github=True)

        output_markdown(content, dest)


################################################################################
# Command-Line-Tools.md functions and formatter classes
################################################################################

def make_cli_source_link():
    """Create a markdown link to ``make_cli_markdown`` function on GitHub.

    Returns:
        str: Formatted link to ``make_cli_markdown`` function on GitHub.
    """
    link = (
        "[`{path}:{func.__name__}()`]"
        "(https://github.com/{repo}/blob/{branch}/{path}#L{start}-L{end})"
    )

    try:
        # Patch inspect.getsourcefile which is called by inspect.getsourcelines
        inspect.getsourcefile = PATCHED_getsourcefile
        lines, start = inspect.getsourcelines(make_cli_markdown)
    finally:
        inspect.getsourcefile = ORIGINAL_getsourcefile

    return link.format(
        func=make_cli_markdown,
        path=os.path.relpath(THIS_FILE, REZ_SOURCE_DIR),
        repo=GITHUB_REPO,
        branch=GITHUB_BRANCH,
        start=start,
        end=start + len(lines),
    )


def make_cli_markdown(src_path):
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
                    r'^\s+(\w+)(\s+)',
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
    """Parser flags, using global variables as defaults."""
    INIT_DEFAULTS = {
        "prog": "update-wiki",
        "description": "Update GitHub Wiki",
        "formatter_class": argparse.ArgumentDefaultsHelpFormatter,
    }

    def __init__(self, **kwargs):
        """Setup default arguments and parser description/program name.

        If no parser description/program name are given, default ones will
        be assigned.

        Args:
            kwargs (dict[str]):
                Same key word arguments taken by
                ``argparse.ArgumentParser.__init__()``
        """
        for key, value in self.INIT_DEFAULTS.items():
            kwargs.setdefault(key, value)
        super(UpdateWikiParser, self).__init__(**kwargs)

        self.add_argument(
            "--no-push",
            action="store_false",
            dest="push",
            help="Don't git commit and push new changes.",
        )
        self.add_argument(
            "--keep-temp",
            action="store_true",
            dest="keep",
            help="Don't remove temporary wiki repository directory.",
        )
        self.add_argument(
            "--github-repo",
            default=GITHUB_REPO,
            dest="repo",
            help=(
                "Url to GitHub repository without leading github.com/. "
                "Overrides environment variable GITHUB_REPOSITORY."
            )
        )
        self.add_argument(
            "--github-branch",
            default=GITHUB_BRANCH,
            dest="branch",
            help=(
                "Name of git branch that is generating the Wiki. "
                "Overrides environment variable GITHUB_BRANCH."
            )
        )
        self.add_argument(
            "--github-workflow",
            default=GITHUB_WORKFLOW,
            dest="workflow",
            help=(
                "Name of GitHub workflow that is generating the Wiki. "
                "Overrides environment variable GITHUB_WORKFLOW."
            )
        )
        self.add_argument(
            "--wiki-url",
            default=CLONE_URL,
            dest="url",
            help=(
                "Use this url to git clone wiki from. "
                "Overrides environment variable CLONE_URL."
            )
        )
        self.add_argument(
            "--wiki-dir",
            default=TEMP_WIKI_DIR,
            dest="dir",
            help=(
                "Use this EMPTY directory to temporarily store cloned wiki. "
                "Overrides environment variable TEMP_WIKI_DIR."
            )
        )


if __name__ == "__main__":
    args = UpdateWikiParser().parse_args()
    CLONE_URL = args.url
    GITHUB_REPO = args.repo
    GITHUB_BRANCH = args.branch
    GITHUB_WORKFLOW = args.workflow
    TEMP_WIKI_DIR = os.path.abspath(args.dir)
    if not os.path.exists(TEMP_WIKI_DIR):
        os.makedirs(TEMP_WIKI_DIR)

    subprocess.check_call(
        ["git", "clone", "--no-checkout", CLONE_URL, TEMP_WIKI_DIR]
    )
    shutil.copytree(
        os.path.join(THIS_DIR, 'media'),
        os.path.join(TEMP_WIKI_DIR, 'media'),
    )
    os.environ['REZ_SOURCE_DIR'] = REZ_SOURCE_DIR

    # python utils/process.py  # Replaced by...
    os.chdir(TEMP_WIKI_DIR)
    process_markdown_files()

    # bash utils/update.sh  # Replaced by...
    subprocess.check_call(['git', 'add', '.'])
    if not args.push:
        subprocess.call(['git', 'status'])
    elif subprocess.call(['git', 'diff', '--quiet', '--staged']):
        # --quiet implies --exit-code, exits with 1 if there were differences
        subprocess.check_call(['git', 'commit', '-m', 'doc update'])
        subprocess.check_call(['git', 'push'])
    else:
        print("No changes to commit and push.")

    os.chdir(THIS_DIR)
    if not args.keep:
        shutil.rmtree(TEMP_WIKI_DIR, ignore_errors=True)
