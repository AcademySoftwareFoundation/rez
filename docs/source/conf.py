# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Add path to rez's source.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

# Add path to the root of the docs folder to get access to the rez_sphinxext extension.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import rez.utils._version

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'rez'
copyright = 'Contributors to the rez project'
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
    "sphinx.ext.todo",
    # Rez custom extension
    'rez_sphinxext'
]

templates_path = ['_templates']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']

html_theme_options = {
    'light_logo': 'rez-icon-black.svg',
    'dark_logo': 'rez-icon-white.svg'
}


# These paths are either relative to html_static_path
# or fully qualified paths (eg. https://...)
html_css_files = [
    'css/custom.css',
]

# -- Options for intersphinx extension ---------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#module-sphinx.ext.intersphinx

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

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
