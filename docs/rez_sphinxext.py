import os
import re

import rez.rezconfig
import docutils.nodes
import sphinx.util.nodes
import sphinx.application
import sphinx.environment
import sphinx.util.docutils
import docutils.statemachine


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
        rst = ['.. currentmodule:: config']

        for section in settings:
            rst.append('')
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
    Special rex-config directive. This is quite similar to "autodoc" in some ways.
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


# https://github.com/sphinx-doc/sphinx/blob/064b6279536da573d31990d7819a110eee98b342/sphinx/builders/__init__.py#L383
# https://github.com/sphinx-doc/sphinx/blob/064b6279536da573d31990d7819a110eee98b342/sphinx/environment/__init__.py#L459
def checkIfRezConfigIsOutdated(
    app: sphinx.application.Sphinx,
    env: sphinx.environment.BuildEnvironment,
    added: set[str],
    changed: set[str],
    removed: set[str],
) -> list[str]:
    """
    Cache invalidation for configuring_rez

    :returns: Documents considered changed.
    """
    rezconfigMtime = -(os.stat(rez.rezconfig.__file__).st_mtime_ns // -1_000)

    # env.all_docs is a dict that contains previously build documents and their timestamp at the time.
    # So we use it to compare the current timestamp of rezconfig.py. if rezconfig.py is more
    # recent, we tell sphinx to re-build the configuring_rez document.
    if 'configuring_rez' not in added and rezconfigMtime > env.all_docs['configuring_rez']:
        return ['configuring_rez']
    return []

def setup(app: sphinx.application.Sphinx) -> dict[str, bool | str]:
    app.setup_extension('sphinx.ext.autodoc')
    app.add_directive('rez-config', RezConfigDirective)
    app.connect('env-get-outdated', checkIfRezConfigIsOutdated)

    return {
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
