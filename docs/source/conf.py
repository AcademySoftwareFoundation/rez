# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

import sphinx.domains
import sphinx.addnodes
import sphinx.application

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
    "myst_parser",
    # Rez custom extension
    'rez_sphinxext'
]

templates_path = ['_templates']

nitpick_ignore = [
    # TODO: Remove once we unvendor enum.
    ("py:class", "rez.solver._Common"),
    ("py:class", "_thread._local"),
    ("py:class", "rez.utils.platform_._UnixPlatform"),
    ("py:class", "rez.version._util._Common"),
    ("py:class", "rez.version._version._Comparable"),
]

nitpick_ignore_regex = [
    ("py:class", r"rez\.vendor\..*"),
]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']

html_theme_options = {
    'light_logo': 'rez-horizontal-black.svg',
    'dark_logo': 'rez-horizontal-white.svg',
    'sidebar_hide_name': True,
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
autodoc_inherit_docstrings = True
autodoc_default_options = {
    "show-inheritance": True,
    "undoc-members": True,
    "inherited-members": True,
}


# -- Options for extlinks extension -----------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/extlinks.html

blob_ref = "main"
if os.environ.get("READTHEDOCS"):
    if os.environ["READTHEDOCS_VERSION_TYPE"] == "external":
        blob_ref = os.environ["READTHEDOCS_GIT_COMMIT_HASH"]
    else:
        blob_ref = os.environ["READTHEDOCS_GIT_IDENTIFIER"]

gh_rez_url = f"https://github.com/AcademySoftwareFoundation/rez/blob/{blob_ref}/%s"

extlinks = {
    'gh-rez': (gh_rez_url, '%s'),
}

# -- Options for todo extension ---------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/todo.html

todo_emit_warnings = False


# -- Custom -----------------------------------------------------------------

def handle_ref_warning(
    app: sphinx.application.Sphinx,
    domain: sphinx.domains.Domain,
    node: sphinx.addnodes.pending_xref,
) -> bool | None:
    """
    Emitted when a cross-reference to an object cannot be resolved even
    after missing-reference. If the event handler can emit warnings for the
    missing reference, it should return True. The configuration variables
    nitpick_ignore and nitpick_ignore_regex prevent the event from being
    emitted for the corresponding nodes.
    """
    if domain and domain.name != 'py':
        return None

    from docutils.utils import get_source_line

    source, line = get_source_line(node)
    if 'docstring of collections.abc.' in source:
        # Silence warnings that come from collections.abc
        return True

    return False


def setup(app: sphinx.application.Sphinx) -> dict[str, bool | str]:
    app.connect('warn-missing-reference', handle_ref_warning)

    return {
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
