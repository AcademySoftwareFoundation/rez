# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""Lightweight Sphinx domains for referencing objects in Rez's documentation.

Rez's own documentation adds its directive implementations in ``rez_sphinxext``.
Consumers only need these domain names and the inherited Python roles for
intersphinx resolution.
"""

from rez.utils import _rez_version

from sphinx.domains.python import PythonDomain

__all__ = ["setup"]


class RexDomain(PythonDomain):
    """Domain for Rex objects used in ``commands()`` functions."""

    name = "rex"
    label = "Rex"


class PkgDefDomain(PythonDomain):
    """Domain for attributes in Rez package definition files."""

    name = "pkgdef"
    label = "Package Definition"


def setup(app):
    """Register Rez's Sphinx domains."""
    app.add_domain(RexDomain)
    app.add_domain(PkgDefDomain)

    return {
        "version": _rez_version,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
