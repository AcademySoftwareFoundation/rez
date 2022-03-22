# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import absolute_import
from rez.bind._utils import find_exe, extract_version, make_dirs, log
from rez.package_maker import make_package
from rez.utils.lint_helper import env
from rez.utils.platform_ import platform_
import os.path
from rez.exceptions import RezBindError
from rez.system import system


def setup_parser(parser):
    parser.add_argument('--exe',
                        type=str,
                        metavar='PATH',
                        help='bind other gcc version than default')


def commands():
    env.PATH.append('{this.root}/bin')


def bind(path, version_range=None, opts=None, parser=None):
    exe_path = getattr(opts, 'exe', None)

    # gcc
    gcc_path = find_exe('gcc', filepath=exe_path)
    gcc_version = extract_version(gcc_path, ['-dumpfullversion', '-dumpversion'])
    log("binding gcc: %s" % gcc_path)

    # g++
    gpp_path = find_exe('g++', filepath=exe_path)
    gpp_version = extract_version(gpp_path, ['-dumpfullversion', '-dumpversion'])
    log("binding g++: %s" % gpp_path)

    if gcc_version != gpp_version:
        raise RezBindError("gcc version different than g++ can not continue")

    # create directories and symlink gcc and g++
    def make_root(variant, root):
        bin_path = make_dirs(root, 'bin')

        gcc_link_path = os.path.join(bin_path, 'gcc')
        platform_.symlink(gcc_path, gcc_link_path)

        gpp_link_path = os.path.join(bin_path, 'g++')
        platform_.symlink(gpp_path, gpp_link_path)

    with make_package('gcc', path, make_root=make_root) as pkg:
        pkg.version = gcc_version
        pkg.tools = ['gcc', 'g++']
        pkg.commands = commands
        pkg.variants = [system.variant]

    return pkg.installed_variants
