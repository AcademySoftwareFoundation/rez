"""
Functions for converting python distributions to rez packages.
"""
from __future__ import print_function
from rez.exceptions import RezSystemError
import pkg_resources
import shutil
import sys
import os
import os.path
import textwrap


def _mkdirs(*dirs):
    path = os.path.join(*dirs)
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def convert_name(name):
    """ Convert a python distribution name into a rez-safe package name."""
    return name.replace('-', '_')


# TODO: change this when version submod is rewritten
# This is just a temporary simplistic implementation for now
def convert_version(version):
    """Convert a python distribution version into a rez-safe version string."""
    """
    version = version.replace('-','.')
    version = version.lower()
    version = re.sub("[a-z]", "", version)
    version = version.replace("..", '.')
    version = version.replace("..", '.')
    version = version.replace("..", '.')
    return version
    """
    return str(version)


# TODO: add native Requirement conversion support into new version submod
def convert_requirement(req):
    """
    Converts a pkg_resources.Requirement object into a list of Rez package
    request strings.
    """
    pkg_name = convert_name(req.project_name)
    if not req.specs:
        return [pkg_name]

    req_strs = []
    for spec in req.specs:
        op, ver = spec
        ver = convert_version(ver)
        if op == "<":
            r = "%s-0+<%s" % (pkg_name, ver)
            req_strs.append(r)
        elif op == "<=":
            r = "%s-0+<%s|%s" % (pkg_name, ver, ver)
            req_strs.append(r)
        elif op == "==":
            r = "%s-%s" % (pkg_name, ver)
            req_strs.append(r)
        elif op == ">=":
            r = "%s-%s+" % (pkg_name, ver)
            req_strs.append(r)
        elif op == ">":
            r1 = "%s-%s+" % (pkg_name, ver)
            r2 = "!%s-%s" % (pkg_name, ver)
            req_strs.append(r1)
            req_strs.append(r2)
        elif op == "!=":
            r = "!%s-%s" % (pkg_name, ver)
            req_strs.append(r)
        else:
            print("Warning: Can't understand op '%s', just depending on unversioned package..." % op, file=sys.stderr)
            req_strs.append(pkg_name)

    return req_strs


def get_dist_dependencies(name, recurse=True):
    """
    Get the dependencies of the given, already installed distribution.
    @param recurse If True, recursively find all dependencies.
    @returns A set of package names.
    @note The first entry in the list is always the top-level package itself.
    """
    dist = pkg_resources.get_distribution(name)
    pkg_name = convert_name(dist.project_name)

    reqs = set()
    working = set([dist])
    depth = 0

    while working:
        deps = set()
        for distname in working:
            dist = pkg_resources.get_distribution(distname)
            pkg_name = convert_name(dist.project_name)
            reqs.add(pkg_name)

            for req in dist.requires():
                reqs_ = convert_requirement(req)
                deps |= set(x.split('-', 1)[0] for x in reqs_
                            if not x.startswith('!'))

        working = deps - reqs
        depth += 1
        if (not recurse) and (depth >= 2):
            break

    return reqs


# TODO: doesn't deal with executable scripts yet
def convert_dist(name, dest_path, make_variant=True, ignore_dirs=None,
                 python_requirement="major_minor"):
    """Convert an already installed python distribution into a rez package.

    Args:
        dest_path (str): Where to put the rez package. The package will be
            created under dest_path/<NAME>/<VERSION>/.
        make_variant (bool): If True, makes a single variant in the rez package
            based on the MAJOR.MINOR version of python.
        ignore_dirs (bool): List of directory names to not copy from the dist.
        python_requirement (str): How the package should depend on python.
            One of:
            - "major": depend on python-X
            - "major_minor": depend on python-X.X
            - any other value: this string is used as the literal version
              range string.

    Returns:
        Install path of the new Rez package.
    """
    dist = pkg_resources.get_distribution(name)
    pkg_name = convert_name(dist.project_name)
    pkg_version = convert_version(dist.version)

    if python_requirement == "major":
        pyver = str(sys.version_info[0])
    elif python_requirement == "major_minor":
        pyver = '.'.join(str(x) for x in sys.version_info[:2])
    else:
        pyver = python_requirement
    pypkg = "python-%s" % pyver

    pkg_requires = []
    if not make_variant:
        pkg_requires.append(pypkg)
    for req in dist.requires():
        pkg_requires += convert_requirement(req)

    pkg_path = _mkdirs(dest_path, pkg_name, pkg_version)
    pkg_file = os.path.join(pkg_path, "package.py")
    root_path = _mkdirs(pkg_path, pypkg) if make_variant else pkg_path

    basename = os.path.basename(dist.location)
    is_egg = (os.path.splitext(basename)[1] == ".egg")

    if os.path.isdir(dist.location):
        if is_egg:
            # this is an egg-dir
            for file in os.listdir(dist.location):
                fpath = os.path.join(dist.location, file)
                if os.path.isfile(fpath):
                    shutil.copy(fpath, root_path)
                else:
                    shutil.copytree(fpath, os.path.join(root_path, file),
                                    ignore=shutil.ignore_patterns(ignore_dirs))
        else:
            # this is a site dir
            egginfo_dir = "%s.egg-info" % dist.egg_name()
            eggpath = os.path.join(dist.location, egginfo_dir)
            file = os.path.join(eggpath, "installed-files.txt")
            if not os.path.isfile(file):
                raise RezSystemError(
                    "There is not enough information on disk to convert the "
                    "python distribution '%s' into a Rez package. The distribution "
                    "is installed to a common site, but the installed file "
                    "information is not present." % name)

            with open(file) as f:
                installed_files = f.read().strip().split()

            dirs = set()
            files = set()
            for file in installed_files:
                path = os.path.join(eggpath, file)
                path = os.path.realpath(path)

                if os.path.isfile(path) and path.startswith(dist.location + os.sep):
                    dir_ = os.path.dirname(path)
                    if ignore_dirs:
                        reldir = os.path.relpath(dir_, dist.location)
                        if set(reldir.split(os.sep)) & set(ignore_dirs):
                            continue

                    files.add(path)
                    dirs.add(dir_)

            def _dst(p):
                dst = os.path.relpath(p, dist.location)
                dst = os.path.join(root_path, dst)
                return os.path.realpath(dst)

            for dir_ in dirs:
                dst_dir = _dst(dir_)
                _mkdirs(dst_dir)

            for file in files:
                dst_file = _dst(file)
                shutil.copy(file, dst_file)
    else:
        # this is an egg-file
        import zipfile
        assert(is_egg and os.path.isfile(dist.location))
        assert(zipfile.is_zipfile(dist.location))
        z = zipfile.ZipFile(dist.location)
        z.extractall(root_path)

    variants_str = "[['%s']]" % pypkg if make_variant else ''

    content = textwrap.dedent(
        """
        config_version = 0
        name = '%(name)s'
        version = '%(version)s'
        %(variants)s
        requires = %(requires)s
        def commands():
            env.PYTHONPATH.append('{this.root}')
        """ % dict(
            name=pkg_name,
            version=pkg_version,
            variants=variants_str,
            requires=str(pkg_requires)))

    content = content.strip() + '\n'
    with open(pkg_file, 'w') as f:
        f.write(content)

    return pkg_path


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
