# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""Resilient access to ``mypy_extensions.mypyc_attr``.

The ``@mypyc_attr`` decorator configures how mypyc compiles a class (eg
``allow_interpreted_subclasses``). It is required when building rez with mypyc
and is a no-op at runtime. ``mypy_extensions`` is a declared runtime
requirement (see ``setup.py``), but it is not importable in every context --
notably ``install.py`` imports rez modules using the system python, before
rez's dependencies have been installed. Import ``mypyc_attr`` from here rather
than directly from ``mypy_extensions`` so that importing rez does not
hard-require ``mypy_extensions``; when it is absent we fall back to a no-op
decorator (which is all it does at runtime anyway).
"""

try:
    from mypy_extensions import mypyc_attr
except ImportError:
    def mypyc_attr(*attrs, **kwattrs):  # type: ignore[misc]
        def deco(x):
            return x
        return deco
