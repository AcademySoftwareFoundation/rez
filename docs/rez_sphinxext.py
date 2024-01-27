import os
import re
import argparse

import rez.cli._main
import rez.cli._util
import rez.rezconfig
import docutils.nodes
import sphinx.util.nodes
import sphinx.application
import sphinx.environment
import sphinx.util.logging
import sphinx.util.docutils
import docutils.statemachine

_LOG = sphinx.util.logging.getLogger(f"ext.{__name__.split('.')[-1]}")


def convert_rez_config_to_rst() -> list[str]:
    with open(rez.rezconfig.__file__) as fd:
        txt = fd.read()

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

        section_header = re.compile(r"^\#{10,}")

        section_title = None
        section_description = None
        end_of_section = 0

        # parse out settings sections, settings and their comment
        for i, line in enumerate(lines):

            if section_header.match(line) and i != end_of_section:
                section_title = lines[i + 1].split('#', 1)[-1].strip()
                section_description = ''
                description_linenumber = i + 2
                end_of_section = description_linenumber

                while not section_header.match(lines[description_linenumber]):
                    section_description += lines[description_linenumber].split('#', 1)[-1].strip() + '\n'
                    description_linenumber += 1
                    end_of_section = description_linenumber

            m = assign_regex.match(line)
            if not m:
                continue

            start_defn = i
            end_defn = i
            while lines[end_defn].strip() and not lines[end_defn].startswith('#'):
                end_defn += 1

            value_lines = lines[start_defn:end_defn]
            value_lines[0] = value_lines[0].split("=")[-1].strip()

            end_comment = i
            while not lines[end_comment].startswith('#'):
                end_comment -= 1

            start_comment = end_comment
            while lines[start_comment].startswith('#'):
                start_comment -= 1
            start_comment += 1

            comments = lines[start_comment:end_comment + 1]
            comment_lines = [x[2:] for x in comments]  # drop leading '# '

            varname = m.groups()[0]
            if section_title in settings:
                settings[section_title]['settings'][varname] = (value_lines, comment_lines)
            else:
                settings[section_title] = {
                    'desc': section_description,
                    'settings': {varname: (value_lines, comment_lines)}
                }

        # generate rst text
        # rst = ['.. currentmodule:: config']
        rst = []

        for section in settings:
            rst.append('')
            rst.append(".. _config-{}:".format(section.replace(' ', '-').lower()))
            rst.append("")
            rst.append(section)
            rst.append("-" * len(section))
            rst.append('')

            # This seems benign (storing each line individually), but it's actually extremelly
            # important. The docutils ViewList class absolutely requires to have only one line per
            # entry. If we don't do that, the docutils parser won't parse the sublines,
            # and we'll get "garbage" (ie unformatted lines) in the output.
            for line in settings[section]['desc'].strip().split('\n'):
                rst.append(line)
            rst.append('')

            for varname, (value_lines, comment_lines) in sorted(settings[section]['settings'].items()):
                rst.append(".. py:data:: {0}".format(varname))
                if len(value_lines) == 1:
                    rst.append("   :value: {0}".format(value_lines[0]))
                else:
                    rst.append('')
                    rst.append('   Default:')
                    rst.append('')
                    rst.append('   .. code-block:: python')
                    rst.append('')
                    for line in value_lines:
                        rst.append(f'      {line}')

                rst.append('')
                for line in comment_lines:
                    rst.append(f'   {line}')
                rst.append('')

                envvar = f'REZ_{varname.upper()}'
                rst.append(f'   .. envvar:: {envvar}')
                rst.append('')
                rst.append(f'      The ``{envvar}`` environment variable can also be used to configure this.')
                rst.append('')

    return rst


# Inspired by https://github.com/pypa/pip/blob/4a79e65cb6aac84505ad92d272a29f0c3c1aedce/docs/pip_sphinxext.py
# https://stackoverflow.com/a/44084890
class RezConfigDirective(sphinx.util.docutils.SphinxDirective):
    """
    Special rez-config directive. This is quite similar to "autodoc" in some ways.
    """
    required_arguments = 0
    optional_arguments = 0

    def run(self) -> list[docutils.nodes.Node]:
        # Create the node.
        node = docutils.nodes.section()
        node.document = self.state.document

        rst = docutils.statemachine.ViewList()

        # Get the configuration settings as reStructuredText text.
        configLines = convert_rez_config_to_rst()

        # Add rezconfig as a dependency to the current document. The document
        # will be rebuilt if rezconfig changes.
        self.env.note_dependency(rez.rezconfig.__file__)
        self.env.note_dependency(__file__)

        path, lineNumber = self.get_source_info()

        # Add each line to the view list.
        for index, line in enumerate(configLines):
            # Note to future people that will look at this.
            # "line" has to be a single line! It can't be a line like "this\nthat".
            rst.append(line, path, lineNumber+index)

        # Finally, convert the rst into the appropriate docutils/sphinx nodes.
        sphinx.util.nodes.nested_parse_with_titles(self.state, rst, node)

        # Return the generated nodes.
        return node.children


class RezAutoArgparseDirective(sphinx.util.docutils.SphinxDirective):
    """
    Special rez-autoargparse directive. This is quite similar to "autosummary" in some ways.
    """
    required_arguments = 0
    optional_arguments = 0

    def run(self) -> list[docutils.nodes.Node]:
        # Create the node.
        node = docutils.nodes.section()
        node.document = self.state.document

        rst = docutils.statemachine.ViewList()

        # Add rezconfig as a dependency to the current document. The document
        # will be rebuilt if rezconfig changes.
        self.env.note_dependency(rez.cli._util.__file__)
        self.env.note_dependency(__file__)

        path, lineNumber = self.get_source_info()

        toc = """.. toctree::
   :maxdepth: 1
   :hidden:

   commands/rez

"""
        listRst = "* :doc:`commands/rez`\n"

        for subcommand, config in rez.cli._util.subcommands.items():
            if config.get('hidden'):
                continue

            toc += f"   commands/rez-{subcommand}\n"
            listRst += f"* :doc:`commands/rez-{subcommand}`\n"

        # Add each line to the view list.
        for index, line in enumerate((toc + "\n" + listRst).split("\n")):
            # Note to future people that will look at this.
            # "line" has to be a single line! It can't be a line like "this\nthat".
            rst.append(line, path, lineNumber+index)

        # Finally, convert the rst into the appropriate docutils/sphinx nodes.
        sphinx.util.nodes.nested_parse_with_titles(self.state, rst, node)

        # Return the generated nodes.
        return node.children


# Inspired by autosummary (https://github.com/sphinx-doc/sphinx/blob/fcc38997f1d9b728bb4ffc64fc362c7763a4ee25/sphinx/ext/autosummary/__init__.py#L782)
# and https://github.com/ashb/sphinx-argparse/blob/b2f42564fb03ede94e94c149a425e398764158ca/sphinxarg/parser.py#L49
def write_cli_documents(app: sphinx.application.Sphinx) -> None:
    """
    Write the CLI pages into the "commands" folder.
    """
    _LOG.info("[rez-autoargparse] generating command line documents")

    _LOG.info("[rez-autoargparse] seting up the parser")
    main_parser = rez.cli._main.setup_parser()
    main_parser._setup_all_subparsers()

    parsers = [main_parser]
    for action in main_parser._actions:
        if isinstance(action, rez.cli._util.LazySubParsersAction):
            parsers += action.choices.values()

    for parser in sorted(parsers, key=lambda x: x.prog):
        full_cmd = parser.prog.replace(' ', '-')

        # Title
        document = [f".. _{full_cmd}:"]
        document.append("")
        document.append(f"{'='*len(parser.prog)}")
        document.append(f"{full_cmd}")
        document.append(f"{'='*len(parser.prog)}")
        document.append("")

        document.append(f".. program:: {full_cmd}")
        document.append("")
        document.append("Usage")
        document.append("=====")
        document.append("")
        document.append(".. code-block:: text")
        document.append("")
        for line in parser.format_usage()[7:].split("\n"):
            document.append(f"   {line}")
        document.append("")

        if parser.description == argparse.SUPPRESS:
            continue

        document.append("description")
        document.append("===========")
        document.extend(parser.description.split("\n"))

        document.append("")
        document.append("Options")
        document.append("=======")
        document.append("")

        for action in parser._action_groups[1]._group_actions:
            if isinstance(action, argparse._HelpAction):
                continue

            # Quote default values for string/None types
            default = action.default
            if action.default not in ['', None, True, False] and action.type in [None, str] and isinstance(action.default, str):
                default = f'"{default}"'

            # fill in any formatters, like %(default)s
            format_dict = dict(vars(action), prog=parser.prog, default=default)
            format_dict['default'] = default
            help_str = action.help or ''  # Ensure we don't print None
            try:
                help_str = help_str % format_dict
            except Exception:
                pass

            if help_str == argparse.SUPPRESS:
                continue

            # Avoid Sphinx warnings.
            help_str = help_str.replace("*", "\\*")
            # Replace everything that looks like an argument with an option directive.
            help_str = re.sub(r"(?<!\w)-[a-zA-Z](?=\s|\/|\)|\.?$)|(?<!\w)--[a-zA-Z-0-9]+(?=\s|\/|\)|\.?$)", r":option:`\g<0>`", help_str)
            help_str = help_str.replace("--", "\\--")

            # Options have the option_strings set, positional arguments don't
            name = action.option_strings
            if name == []:
                if action.metavar is None:
                    name = [action.dest]
                else:
                    name = [action.metavar]

            # Skip lines for subcommands
            if name == [argparse.SUPPRESS]:
                continue

            metavar = f"<{action.metavar}>" if action.metavar else ""
            document.append(f".. option:: {', '.join(name)} {metavar.lower()}")
            document.append("")
            document.append(f"   {help_str}")
            if action.choices:
                document.append("")
                document.append(f"   Choices: {', '.join(action.choices)}")
            document.append("")

        document = "\n".join(document)

        dest = os.path.join(app.srcdir, "commands", f"{full_cmd}.rst")
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        if os.path.exists(dest):
            with open(dest, "r") as fd:
                if fd.read() == document:
                    # Documents are the same, skip writing to avoid
                    # invalidating Sphinx's cache.
                    continue

        with open(dest, "w") as fd:
            fd.write(document)


def setup(app: sphinx.application.Sphinx) -> dict[str, bool | str]:
    app.setup_extension('sphinx.ext.autodoc')
    app.add_directive('rez-config', RezConfigDirective)

    app.connect('builder-inited', write_cli_documents)
    app.add_directive('rez-autoargparse', RezAutoArgparseDirective)

    return {
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
