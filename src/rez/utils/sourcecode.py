from rez.utils.formatting import indent
from rez.utils.data_utils import cached_property
from rez.utils.logging_ import print_debug
from inspect import getsourcelines
from textwrap import dedent
from glob import glob
import traceback
import os.path
import imp


def early():
    """Used by functions in package.py to harden to the return value at build time.

    The term 'early' refers to the fact these package attribute are evaluated
    early, ie at build time and before a package is installed.
    """
    def decorated(fn):
        setattr(fn, "_early", True)
        return fn

    return decorated


def late():
    """Used by functions in package.py that are evaluated lazily.

    The term 'late' refers to the fact these package attributes are evaluated
    late, ie when the attribute is queried for the first time.

    If you want to implement a package.py attribute as a function, you MUST use
    this decorator - otherwise it is understood that you want your attribute to
    be a function, not the return value of that function.
    """
    def decorated(fn):
        setattr(fn, "_late", True)
        _add_decorator(fn, "late")
        return fn

    return decorated


def include(module_name, *module_names):
    """Used by functions in package.py to have access to named modules.

    See the 'package_definition_python_path' config setting for more info.
    """
    def decorated(fn):
        _add_decorator(fn, "include", nargs=[module_name] + list(module_names))
        return fn

    return decorated


def _add_decorator(fn, name, **kwargs):
    if not hasattr(fn, "_decorators"):
        setattr(fn, "_decorators", [])

    kwargs.update({"name": name})
    fn._decorators.append(kwargs)


class SourceCodeError(Exception):
    pass


class SourceCodeCompileError(Exception):
    pass


class SourceCodeExecError(Exception):
    pass


class SourceCode(object):
    """Wrapper for python source code.

    This object is aware of the decorators defined in this sourcefile (such as
    'include') and deals with them appropriately.
    """
    def __init__(self, source, func=None, filepath=None):
        self.source = source.rstrip()
        self.func = func
        self.filepath = filepath
        self.package = None

    def copy(self):
        other = SourceCode(source=self.source, func=self.func)
        return other

    # TODO this breaks in cases like: comment after decorator and before sig;
    # sig broken over multiple lines, etc
    @classmethod
    def from_function(cls, func, filepath=None):
        # get txt of function body. Skips sig and any decorators. Assumes that
        # only the decorators in this file (such as 'include') are used.
        num_decorators = len(getattr(func, "_decorators", []))
        loc = getsourcelines(func)[0][num_decorators + 1:]
        code = dedent(''.join(loc))

        # align lines that start with a comment (#)
        codelines = code.split('\n')
        linescount = len(codelines)

        for i, line in enumerate(codelines):
            if line.startswith('#'):
                nextindex = i + 1 if i < linescount else i - 1
                nextline = codelines[nextindex]

                while nextline.startswith('#'):
                    nextline = codelines[nextindex]
                    nextindex = (nextindex + 1 if nextindex < linescount
                                 else nextindex - 1)

                firstchar = len(nextline) - len(nextline.lstrip())
                codelines[i] = '%s%s' % (nextline[:firstchar], line)

        code = '\n'.join(codelines).rstrip()
        code = dedent(code)

        value = SourceCode.__new__(SourceCode)
        value.source = code
        value.func = func
        value.filepath = filepath
        value.package = None

        return value

    @cached_property
    def includes(self):
        info = self._get_decorator_info("include")
        if not info:
            return None

        return set(info.get("nargs", []))

    @cached_property
    def late_binding(self):
        info = self._get_decorator_info("late")
        return bool(info)

    @cached_property
    def evaluated_code(self):
        # turn into a function, because code may use return clause
        if self.func:
            funcname = self.func.__name__
        else:
            funcname = "_unnamed"

        code = indent(self.source)
        code = ("def %s():\n" % funcname
                + code
                + "\n_result = %s()" % funcname)

        return code

    @property
    def sourcename(self):
        if self.filepath:
            filename = self.filepath
        else:
            filename = "string"

        if self.func:
            filename += ":%s" % self.func.__name__

        return "<%s>" % filename

    @property
    def function_name(self):
        if self.func:
            return self.func.__name__
        else:
            return None

    @cached_property
    def compiled(self):
        try:
            pyc = compile(self.evaluated_code, self.sourcename, 'exec')
        except Exception as e:
            stack = traceback.format_exc()
            raise SourceCodeCompileError(
                "Failed to compile %s:\n\n%s" % (self.sourcename, stack))

        return pyc

    def set_package(self, package):
        # this is needed to load @included modules
        self.package = package

    def exec_(self, globals_={}):
        # bind import modules
        if self.package is not None:
            if self.includes:
                globals_ = globals_.copy()

                for name in self.includes:
                    module = include_module_manager.load_module(name, self.package)
                    globals_[name] = module

        # exec
        pyc = self.compiled

        try:
            exec pyc in globals_
        except Exception as e:
            stack = traceback.format_exc()
            raise SourceCodeExecError(
                "Failed to execute %s:\n\n%s" % (self.sourcename, stack))

        return globals_.get("_result")

    def to_text(self, funcname):
        # don't indent code if already indented
        if self.source[0] in (' ', '\t'):
            source = self.source
        else:
            source = indent(self.source)

        txt = "def %s():\n%s" % (funcname, source)

        if self.func and hasattr(self.func, "_decorators"):
            for entry in self.func._decorators:
                nargs_str = ", ".join(map(repr, entry.get("nargs", [])))
                name_str = entry.get("name")
                sig = "@%s(%s)" % (name_str, nargs_str)

                txt = sig + '\n' + txt

        return txt

    def _get_decorator_info(self, name):
        if not self.func:
            return None

        if not hasattr(self.func, "_decorators"):
            return None

        matches = [x for x in self.func._decorators if x.get("name") == name]
        if not matches:
            return None

        return matches[0]

    def __eq__(self, other):
        return (isinstance(other, SourceCode)
                and other.source == self.source)

    def __ne__(self, other):
        return not (other == self)

    def __str__(self):
        return self.source

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.source)


class IncludeModuleManager(object):
    """Manages a cache of modules imported via '@include' decorator.
    """

    # subdirectory under package 'base' path where we expect to find copied
    # sourcefiles referred to by the '@include' function decorator.
    #
    include_modules_subpath = ".rez/include"

    def __init__(self):
        self.modules = {}

    def load_module(self, name, package):
        from rez.config import config  # avoiding circular import

        path = os.path.join(package.base, self.include_modules_subpath)
        pathname = os.path.join(path, "%s-*.py" % name)

        pathnames = glob(pathname)
        if not pathnames:
            return None

        filepath = pathnames[0]
        hash_str = filepath.rsplit('-', 1)[-1].split('.', 1)[0]

        module = self.modules.get(hash_str)
        if module is not None:
            return module

        if config.debug("file_loads"):
            print_debug("Loading include sourcefile: %s" % filepath)

        with open(filepath) as f:
            module = imp.load_source(name, filepath, f)

        self.modules[hash_str] = module
        return module


# singleton
include_module_manager = IncludeModuleManager()
