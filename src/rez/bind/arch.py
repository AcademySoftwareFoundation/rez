# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Creates the system architecture package.
"""
from __future__ import absolute_import
from rez.package_maker import make_package
from rez.vendor.version.version import Version
from rez.bind._utils import check_version
from rez.system import system


def bind(path, version_range=None, opts=None, parser=None):
    version = Version(system.arch)
    check_version(version, version_range)

    with make_package("arch", path) as pkg:
        pkg.version = version

    return pkg.installed_variants
