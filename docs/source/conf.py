# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import re
import sys
import textwrap

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

import rez.utils._version

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'rez'
copyright = '2023, Contributors to the rez project'
author = 'Contributors to the rez project'
version = rez.utils._version._rez_version
release = rez.utils._version._rez_version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.todo",
]

templates_path = ['_templates']
exclude_patterns = [
    'api/rez.cli.*',
    'api/rez.vendor.[!v]*',
    'api/rez.tests.*'
]



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']


# -- Options for intersphinx extension ---------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#module-sphinx.ext.intersphinx

intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}

# -- Options for autodoc extension ------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#module-sphinx.ext.autodoc

# autoclass_content = 'both'
autodoc_class_signature = 'separated'
autodoc_member_order = 'bysource'


# -- Options for extlinks extension -----------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/extlinks.html

extlinks = {
    'gh-rez': ('https://github.com/AcademySoftwareFoundation/rez/blob/master/%s', '%s'),
}

# -- Options for todo extension ---------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/todo.html

todo_emit_warnings = True


def populate_rez_config(app, config):
    filepath = os.path.abspath(os.path.join(__file__, '..', '..', '..', "src", "rez", "rezconfig.py"))

    with open(filepath) as fd:
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

                # print('Reading description')
                while not section_header.match(lines[description_linenumber]):
                    # print(description_linenumber+start, lines[description_linenumber])
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
            value = '\n'.join(value_lines)

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
            # print(varname)
            if section_title in settings:
                settings[section_title]['settings'][varname] = (value, comment)
            else:
                # print('Adding new section named {0!r} with description {1!r}'.format(section_title, section_description))
                settings[section_title] = {
                    'desc': section_description,
                    'settings': {varname: (value, comment)}
                }


        # generate md text
        rst = ['.. currentmodule:: config']

        for section in settings:
            rst.append('')
            rst.append(section)
            rst.append("-" * len(section))
            rst.append('')

            rst.append(settings[section]['desc'].strip())
            rst.append('')

            for varname, (value, comment) in sorted(settings[section]['settings'].items()):
                rst.append(".. py:data:: {0}".format(varname))
                if len(value.split('\n')) == 1:
                    rst.append("   :value: {0}".format(value))
                else:
                    rst.append('')
                    rst.append('   Default:')
                    rst.append('')
                    rst.append('   .. code-block:: python')
                    rst.append('')
                    rst.append(textwrap.indent(value, '      '))

                rst.append('')
                rst.append(textwrap.indent(comment, '   '))
                rst.append('')

                envvar = f'REZ_{varname.upper()}'
                rst.append(f'   .. envvar:: {envvar}')
                rst.append('')
                rst.append(f'      The ``{envvar}`` environment variable can also be used to configure this.')

        rst = '\n'.join(rst)

    with open(os.path.join(os.path.dirname(__file__), '_configuring_rez.rst.in'), 'r') as fd:
        new_text = fd.read().replace('__REZCONFIG__', rst)

    with open(os.path.join(os.path.dirname(__file__), 'configuring_rez.rst'), 'w') as fd:
        fd.write(new_text)


def onDoctreeRead(app, doctree):
    domain = app.env.get_domain('std')
    domain.note_object('asd', 'envvar', 'asd')

def setup(app):
    app.connect('config-inited', populate_rez_config)
