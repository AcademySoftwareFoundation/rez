"""Make Rez Packages.

Whilst a lot of packages are created via the rez build process, there are
other cases where packages need to be built. For example - creating packages
for unit tests, and creating packages that bind existing installed software
to Rez. This module provides a means to create packages directly. Example:

    with make_py_package('foo-1.0', path) as pkg:
        pkg.set_requires("python")
        pkg.set_tools("hello_world")

To see more examples of making packages, look at the builtin 'bind modules',
in the rez/bind/ subdirectory.
"""
from rez.vendor.version.version import Version
from rez.vendor.version.requirement import Requirement, RequirementList
from rez.vendor import yaml
from rez.exceptions import PackageMetadataError, RezSystemError
from rez.util import OrderedDict
from rez.utils.yaml import dump_package_yaml
from contextlib import contextmanager
import inspect
import textwrap
import os
import os.path
import stat


class quoted(str):
    """Wrap a string in this class to force a quoted representation when written
    to the package definition file."""
    pass


class literal(str):
    """Wrap a string in this class to force a (multi-line) representation when
    written to the package definition file."""
    pass

# create a shortcut that is more rez-friendly
rex = literal


class base(object):
    """Describes a path relative to the base of a package. For example, to
    define a 'bin' path relative to a package base: base("bin")."""
    def __init__(self, *dirs):
        self.dirs = dirs

    def __hash__(self):
        return hash(tuple(self.dirs))


class root(object):
    """Describes a path relative to the root of a package variant. There are
    two forms:
        root("bin") creates a 'bin' dir relative to the root of all variants;
        root("bin")(0,1) creates a 'bin' dir only for variants 0 and 1.
    """
    def __init__(self, *dirs):
        self.dirs = dirs
        self.variant_indices = set()

    def __call__(self, *indices):
        self.variant_indices |= set(indices)
        return self

    def __hash__(self):
        return hash((tuple(self.dirs), frozenset(self.variant_indices)))


def quoted_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
yaml.add_representer(quoted, quoted_presenter)


def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
yaml.add_representer(literal, literal_presenter)


def ordered_dict_presenter(dumper, data):
    return dumper.represent_dict(data.items())
yaml.add_representer(OrderedDict, ordered_dict_presenter)


def _entab(text, spaces=4):
    return '\n'.join([(' ' * 4) + t for t in text.split('\n')])


class code_provider(object):
    """Function decorator for functions that only serve to provide code for a
    package maker. This decorator stops the function from being run directly.
    """
    def __init__(self, fn):
        self._fn = fn

    def __call__(self, *args, **kwargs):
        raise RezSystemError("a code provider function was called directly")


def get_code(value):
    n = 1
    if isinstance(value, code_provider):
        value = value._fn
        n += 1
    if inspect.isfunction(value):
        loc = inspect.getsourcelines(value)[0][n:]
        return textwrap.dedent(''.join(loc))
    else:
        return None


class PackageMaker(object):
    """Abstract base class for creating Rez packages.
    """
    def __init__(self, name, version, path):
        """Create a package maker.

        Args:
            name: Name of the package, eg "maya".
            version: Version of the package, either str or Version object.
            path: Path to create the package in. Note that the actual path the
                package will be written to will be (for eg) "{path}/foo/1.2".
        """
        self.path = path
        self.name = name
        self.version = version
        if isinstance(self.version, basestring):
            self.version = Version(self.version)

        self.variants = None
        self.requires = None
        self.build_requires = None
        self.private_build_requires = None
        self.tools = None
        self.commands = None

        self.python_tools = {}
        self.links = set()

    def set_requires(self, *names):
        """Set the requirements of the package."""
        self.requires = [Requirement(x) for x in names]

    def set_build_requires(self, *names):
        """Set the build requirements of the package."""
        self.build_requires = [Requirement(x) for x in names]

    def set_private_build_requires(self, *names):
        """Set the private build requirements of the package."""
        self.private_build_requires = [Requirement(x) for x in names]

    def set_tools(self, *names):
        """Set the tools of the package."""
        self.tools = names

    def set_commands(self, body):
        """Set the commands of the package.

        Args:
            body: One of:
                - str: literal rex code;
                - function: A function containing rex code. Ideally this
                  function is decorated with @code_provider
        """
        self.commands = body

    def add_variant(self, *requires):
        """Add a variant to the package.

        Returns:
            Zero-based variant index.
        """
        self.variants = (self.variants or [])
        self.variants.append([Requirement(x) for x in requires])
        return len(self.variants) - 1

    def add_link(self, source, relpath):
        """Add a symbolic link or equivalent to the package.

        Args:
            source: Path to link to.
            relpath: Path to write the link to. Either a str, `base` or `root`
                object. A string is treated as `base`.
        """
        self.links.add((source, relpath))

    def add_python_tool(self, name, body, relpath):
        """Add a python-based tool to the package.

        Args:
            name: Name of the tool, the executable filename will be based on
                this (on Linux, it will match the filename).
            body: Either a function object or string, providing the code for
                the tool. If a shebang is included, it is ignored.
            relpath: Path to write the tool to. Either a str, `base` or `root`
                object. A string is treated as `base`.

        Note:
            This function does not add the tool to the list of tools, you need
            to include it via set_tools() explicitly.
        """
        self.python_tools[(name, relpath)] = body

    @property
    def base_path(self):
        """Returns the base path containing the package."""
        basedir = os.path.join(self.path, self.name)
        if self.version:
            basedir = os.path.join(basedir, str(self.version))
        return basedir

    @property
    def num_variants(self):
        """Returns the number of variants in the package."""
        return len(self.variants or [])

    def variant_path(self, index=0):
        """Returns the root path of the given variant."""
        if index not in range(len(self.variants)):
            raise IndexError("variant index out of range")

        base = self.base_path
        requires = self.variants[index]
        dirs = [x.safe_str() for x in requires]
        return os.path.join(base, *dirs)

    def flush(self):
        """Write out directories and files that make up the package.
        """
        # sanity check requirements
        for var_requires in (self.variants or [[]]):
            reqs = (self.requires or []) + \
                   (self.build_requires or []) + \
                   (self.private_build_requires or []) + \
                   (var_requires)
            reqlist = RequirementList(reqs)
            if reqlist.conflict:
                raise PackageMetadataError("The package contains an internal "
                                           "conflict: %s" % str(reqlist))

        # make base dir. Variant dirs are created only if needed
        os.makedirs(self.base_path)

        # make python tools
        for (name, path), body in self.python_tools.iteritems():
            if isinstance(body, basestring):
                code = body
            else:
                code = get_code(body)
                assert(code is not None)

            # TODO windows
            for path_ in self._get_paths(path):
                if not os.path.exists(path_):
                    os.makedirs(path_)
                file = os.path.join(path_, name)
                with open(file, 'w') as f:
                    f.write("#!/usr/bin/env python\n")
                    f.write(code)

                os.chmod(file, stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                         | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        # make symlinks
        for (source, path) in self.links:
            for path_ in self._get_paths(path):
                dir_ = os.path.dirname(path_)
                if not os.path.exists(dir_):
                    os.makedirs(dir_)
                # TODO windows
                os.symlink(source, path_)

    def _get_metadata(self):
        doc = OrderedDict(config_version=0,
                          name=self.name,
                          version=str(self.version))

        if self.requires:
            doc["requires"] = [str(x) for x in self.requires]
        if self.build_requires:
            doc["build_requires"] = [str(x) for x in self.build_requires]
        if self.private_build_requires:
            doc["private_build_requires"] = [str(x) for x in self.private_build_requires]

        if self.variants:
            variants = []
            for variant in self.variants:
                requires = [str(x) for x in variant]
                variants.append(requires)
            doc["variants"] = variants

        if self.tools:
            doc["tools"] = [str(x) for x in self.tools]

        if self.commands:
            doc["commands"] = self.commands

        return doc

    def _get_paths(self, relpath):
        if isinstance(relpath, basestring):
            return [os.path.join(self.base_path, relpath)]
        elif isinstance(relpath, base):
            return [os.path.join(self.base_path, *(relpath.dirs))]
        else:
            assert(isinstance(relpath, root))
            if self.num_variants:
                paths = []
                for i in range(self.num_variants):
                    if (not relpath.variant_indices) or (i in relpath.variant_indices):
                        path = os.path.join(self.variant_path(i), *(relpath.dirs))
                        paths.append(path)
                return paths
            elif not relpath.variant_indices:
                return [os.path.join(self.base_path, *(relpath.dirs))]

        return []


class PyPackageMaker(PackageMaker):
    """Create a package.py-based package."""
    def flush(self):
        super(PyPackageMaker, self).flush()

        body = ""
        for key, value in self._get_metadata().iteritems():
            if isinstance(value, rex):
                text = 'def %s():\n%s\n' % (key, _entab(value))
            elif inspect.isfunction(value) or isinstance(value, code_provider):
                code = get_code(value)
                text = 'def %s():\n%s\n' % (key, _entab(code))
            else:
                text = '%s = %r\n' % (key, value)
            body += text + '\n'

        metafile = os.path.join(self.base_path, "package.py")
        with open(metafile, 'w') as f:
            f.write(body.strip() + '\n')


class YamlPackageMaker(PackageMaker):
    """Create a package.yaml-based package."""
    def flush(self):
        super(YamlPackageMaker, self).flush()

        doc = OrderedDict()
        for key, value in self._get_metadata().iteritems():
            if inspect.isfunction(value) or isinstance(value, code_provider):
                code = get_code(value)
                value = rex(code)
            elif key == "commands" and not isinstance(value, rex):
                value = rex(value)

            doc[key] = value

        metafile = os.path.join(self.base_path, "package.yaml")
        with open(metafile, 'w') as f:
            dump_package_yaml(doc, f)


def _make_package(maker):
    yield maker

    # post-with-block:
    maker.flush()
    # TODO create in tmpdir first, validate, then move. Then we could have
    # separate code that deals with merging the package in with an existing
    # package that might have other variants. We could then reuse this code
    # if we end up with a rez-installer-type tool.


@contextmanager
def make_py_package(name, version, path):
    return _make_package(PyPackageMaker(name, version, path))


@contextmanager
def make_yaml_package(name, version, path):
    return _make_package(YamlPackageMaker(name, version, path))
