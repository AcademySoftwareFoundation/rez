from rez.utils.formatting import indent
from rez.utils.data_utils import cached_property
from rez.utils.logging_ import print_debug
from rez.utils import py23
from inspect import getsourcelines
from textwrap import dedent
from glob import glob
import traceback
import os.path


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
    from rez.package_resources import package_rex_keys

    def decorated(fn):

        # this is done here rather than in standard schema validation because
        # the latter causes a very obfuscated error message
        if fn.__name__ in package_rex_keys:
            raise ValueError("Cannot use @late decorator on function '%s'"
                             % fn.__name__)

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
    def __init__(self, msg, short_msg):
        super(SourceCodeError, self).__init__(msg)
        self.short_msg = short_msg


class SourceCodeCompileError(SourceCodeError):
    pass


class SourceCodeExecError(SourceCodeError):
    pass


class SourceCode(object):
    """Wrapper for python source code.

    This object is aware of the decorators defined in this sourcefile (such as
    'include') and deals with them appropriately.
    """
    def __init__(self, source=None, func=None, filepath=None,
                 eval_as_function=True):
        self.source = (source or '').rstrip()
        self.func = func
        self.filepath = filepath
        self.eval_as_function = eval_as_function
        self.package = None

        self.funcname = None
        self.decorators = []

        if self.func is not None:
            self._init_from_func()

    def copy(self):
        other = SourceCode.__new__(SourceCode)
        other.source = self.source
        other.func = self.func
        other.filepath = self.filepath
        other.eval_as_function = self.eval_as_function
        other.package = self.package
        other.funcname = self.funcname
        other.decorators = self.decorators

        return other

    def _init_from_func(self):
        self.funcname = self.func.__name__
        self.decorators = getattr(self.func, "_decorators", [])

        # get txt of function body. Skips sig and any decorators. Assumes that
        # only the decorators in this file (such as 'include') are used.
        loc = getsourcelines(self.func)[0][len(self.decorators) + 1:]
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

        self.source = code

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
        if self.eval_as_function:
            funcname = self.funcname or "_unnamed"

            code = indent(self.source)
            code = (
                "def %s():\n" % funcname
                + code
                + "\n_result = %s()" % funcname
            )
        else:
            code = "if True:\n" + indent(self.source)

        return code

    @property
    def sourcename(self):
        if self.filepath:
            filename = self.filepath
        else:
            filename = "string"

        if self.funcname:
            filename += ":%s" % self.funcname

        return "<%s>" % filename

    @cached_property
    def compiled(self):
        try:
            pyc = compile(self.evaluated_code, self.sourcename, 'exec')
        except Exception as e:
            stack = traceback.format_exc()
            raise SourceCodeCompileError(
                "Failed to compile %s:\n%s" % (self.sourcename, stack),
                short_msg=str(e))

        return pyc

    def set_package(self, package):
        # this is needed to load @included modules
        self.package = package

    def exec_(self, globals_={}):
        # bind import modules
        if self.package is not None and self.includes:
            for name in self.includes:
                module = include_module_manager.load_module(name, self.package)
                globals_[name] = module

        # exec
        pyc = self.compiled

        try:
            exec(pyc, globals_)
        except Exception as e:
            stack = traceback.format_exc()
            raise SourceCodeExecError(
                "Failed to execute %s:\n%s" % (self.sourcename, stack),
                short_msg=str(e))

        return globals_.get("_result")

    def to_text(self, funcname):
        # don't indent code if already indented
        if self.source[0] in (' ', '\t'):
            source = self.source
        else:
            source = indent(self.source)

        txt = "def %s():\n%s" % (funcname, source)

        for entry in self.decorators:
            nargs_str = ", ".join(map(repr, entry.get("nargs", [])))
            name_str = entry.get("name")
            sig = "@%s(%s)" % (name_str, nargs_str)

            txt = sig + '\n' + txt

        return txt

    def _get_decorator_info(self, name):
        matches = [x for x in self.decorators if x.get("name") == name]
        if not matches:
            return None

        return matches[0]

    def __getstate__(self):
        return {
            "source": self.source,
            "filepath": self.filepath,
            "funcname": self.funcname,
            "eval_as_function": self.eval_as_function,
            "decorators": self.decorators
        }

    def __setstate__(self, state):
        self.source = state["source"]
        self.filepath = state["filepath"]
        self.funcname = state["funcname"]
        self.eval_as_function = state["eval_as_function"]
        self.decorators = state["decorators"]

        self.func = None
        self.package = None

    def __eq__(self, other):
        return (
            isinstance(other, SourceCode)
            and other.source == self.source
        )

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
        from hashlib import sha1
        from rez.config import config  # avoiding circular import
        from rez.developer_package import DeveloperPackage

        # in rare cases, a @late bound function may get called before the
        # package is built. An example is 'requires' and the other requires-like
        # functions. These need to be evaluated before a build, but it does also
        # make sense to sometimes implement these as late-bound functions. We
        # detect this case here, and load the modules from the original (pre-
        # copied into package payload) location.
        #
        if isinstance(package, DeveloperPackage):
            # load sourcefile from original location
            path = config.package_definition_python_path
            filepath = os.path.join(path, "%s.py" % name)

            if not os.path.exists(filepath):
                return None

            with open(filepath, "rb") as f:
                hash_str = sha1(f.read().strip()).hexdigest()

        else:
            # load sourcefile that's been copied into package install payload
            path = os.path.join(package.base, self.include_modules_subpath)
            pathname = os.path.join(path, "%s.py" % name)
            hashname = os.path.join(path, "%s.sha1" % name)

            if os.path.isfile(pathname) and os.path.isfile(hashname):
                with open(hashname, "r") as f:
                    hash_str = f.readline()
                filepath = pathname

            else:
                # Fallback for backward compat
                pathname = os.path.join(path, "%s-*.py" % name)
                hashnames = glob(pathname)
                if not hashnames:
                    return None

                filepath = hashnames[0]
                hash_str = filepath.rsplit('-', 1)[-1].split('.', 1)[0]
                # End, for details of backward compat,
                # see https://github.com/nerdvegas/rez/issues/934
                # and https://github.com/nerdvegas/rez/pull/935

        module = self.modules.get(hash_str)
        if module is not None:
            return module

        if config.debug("file_loads"):
            print_debug("Loading include sourcefile: %s" % filepath)

        module = py23.load_module_from_file(name, filepath)
        self.modules[hash_str] = module
        return module


# singleton
include_module_manager = IncludeModuleManager()
