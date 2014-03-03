"""
Functions for converting python distributions to rez packages.
"""
from rez.util import _mkdirs
import pkg_resources
import shutil
import sys
import re
import os
import os.path
import textwrap



def convert_name(name):
    """ Convert a python distribution name into a rez-safe package name."""
    return name.replace('-','_')


# TODO change this when version submod is rewritten
# This is just a temporary simplistic implementation for now
def convert_version(version):
    """Convert a python distribution version into a rez-safe version string."""
    version = version.replace('-','.')
    version = version.lower()
    version = re.sub("[a-z]", "", version)
    version = version.replace("..", '.')
    version = version.replace("..", '.')
    version = version.replace("..", '.')
    return version


# TODO add native Requirement conversion support into new version submod
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
            print >> sys.stderr, \
                "Warning: Can't understand op '%s', just depending on unversioned package..." % op
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
    pkg_version = dist.version

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
                deps |= set(x.split('-',1)[0] for x in reqs_ \
                    if not x.startswith('!'))

        working = deps - reqs
        depth += 1
        if (not recurse) and (depth >= 2):
            break

    return reqs


# TODO doesn't deal with executable scripts yet
def convert_dist(name, dest_path, make_variant=True, ignore=None):
    """
    Convert an already installed python distribution into a rez package.
    @param dest_path Where to put the rez package. The package will be created
        under dest_path/<NAME>/<VERSION>/.
    @param make_variant If True, makes a single variant in the rez package
        based on the MAJOR.MINOR version of python.
    @param ignore Used as ignore param when copying dist src using shutil.copytree.
        This is used internally by Rez, it is unlikely you will need to use it.
    @returns Install path of the new Rez package.
    """
    dist = pkg_resources.get_distribution(name)
    pkg_name = convert_name(dist.project_name)
    pkg_version = convert_version(dist.version)

    pyver = '.'.join(str(x) for x in sys.version_info[:2])
    pypkg = "python-%s" % pyver

    pkg_requires = []
    if not make_variant:
        pkg_requires.append(pypkg)
    for req in dist.requires():
        pkg_requires += convert_requirement(req)

    pkg_path = _mkdirs(dest_path, pkg_name, pkg_version)
    pkg_file = os.path.join(pkg_path, "package.py")
    root_path = _mkdirs(pkg_path, pypkg) if make_variant else pkg_path

    dirname,basename = os.path.split(dist.location)
    is_egg = (os.path.splitext(basename)[1] == ".egg")
    rel_pypath = None

    if os.path.isdir(dist.location):
        rel_pypath = ''
        for file in os.listdir(dist.location):
            fpath = os.path.join(dist.location, file)
            if os.path.isfile(fpath):
                shutil.copy(fpath, root_path)
            else:
                shutil.copytree(fpath, os.path.join(root_path, file), ignore=ignore)
    else:
        import zipfile
        assert(is_egg and os.path.isfile(dist.location))
        assert(zipfile.is_zipfile(dist.location))
        z = zipfile.ZipFile(dist.location)
        z.extractall(root_path)

    variants_str = "[['%s']]" % pypkg if make_variant else ''

    content = textwrap.dedent( \
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
