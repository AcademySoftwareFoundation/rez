from __future__ import with_statement
import os
import subprocess
import sys
import posixpath
import ntpath
from string import Formatter, Template
import re
import UserDict
import inspect
import textwrap
import pipes
import time
import getpass
from rez import module_root_path
from rez.system import system
from rez.settings import settings
from rez.util import print_warning_once, AttrDictWrapper, shlex_join, \
    get_script_path
from rez.exceptions import PkgCommandError


DEFAULT_ENV_SEP_MAP = {'CMAKE_MODULE_PATH': ';'}


_varprog = None

# Expand paths containing shell variable substitutions.
# This expands the forms $variable and ${variable} only.
# Non-existent variables are left unchanged.
def expandvars(path, environ):
    """Expand shell variables of form $var and ${var}.  Unknown variables
    are left unchanged."""
    global _varprog
    if '$' not in path:
        return path
    if not _varprog:
        import re
        _varprog = re.compile(r'\$(\w+|\{[^}]*\})')
    i = 0
    while True:
        m = _varprog.search(path, i)
        if not m:
            break
        i, j = m.span(0)
        name = m.group(1)
        if name.startswith('{') and name.endswith('}'):
            name = name[1:-1]
        if name in environ:
            tail = path[j:]
            path = path[:i] + environ[name]
            i = len(path)
            path += tail
        else:
            i = j
    return path


#===============================================================================
# Actions
#===============================================================================

class Action(object):
    _registry = []

    def __init__(self, *args):
        self.args = args

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__,
                           ', '.join(repr(x) for x in self.args))

    def __eq__(self, other):
        return (self.name == other.name) and (self.args == other.args)

    @classmethod
    def register_command_type(cls, name, klass):
        cls._registry.append((name, klass))

    @classmethod
    def register(cls):
        cls.register_command_type(cls.name, cls)

    @classmethod
    def get_command_types(cls):
        return tuple(cls._registry)

class EnvAction(Action):
    @property
    def key(self):
        return self.args[0]

    @property
    def value(self):
        if len(self.args) == 2:
            return self.args[1]

class Unsetenv(EnvAction):
    name = 'unsetenv'
Unsetenv.register()

class Setenv(EnvAction):
    name = 'setenv'

    def pre_exec(self, interpreter):
        key, value = self.args
        if isinstance(value, (list, tuple)):
            value = interpreter._env_sep(key).join(value)
            self.args = key, value

    def post_exec(self, interpreter, result):
        interpreter._environ.add(self.key)
        return result
Setenv.register()

class Resetenv(EnvAction):
    name = 'resetenv'

    @property
    def friends(self):
        if len(self.args) == 3:
            return self.args[2]

    def pre_exec(self, interpreter):
        key, value, friends = self.args
        if isinstance(value, (list, tuple)):
            value = interpreter._env_sep(key).join(value)
            self.args = key, value, friends

    def post_exec(self, interpreter, result):
        interpreter._environ.add(self.key)
        return result
Resetenv.register()

class Prependenv(Setenv):
    name = 'prependenv'
Prependenv.register()

class Appendenv(Setenv):
    name = 'appendenv'
Appendenv.register()

class Alias(Action):
    name = 'alias'
Alias.register()

class Info(Action):
    name = 'info'
Info.register()

class Error(Action):
    name = 'error'
Error.register()

class Command(Action):
    name = 'command'
Command.register()

class Comment(Action):
    name = 'comment'
Comment.register()

class Source(Action):
    name = 'source'
Source.register()

class Shebang(Action):
    name = 'shebang'
Shebang.register()


#===============================================================================
# Action Manager
#===============================================================================

class ActionManager(object):
    """
    Handles the execution book-keeping.  Tracks env variable values, and
    triggers the callbacks of the `ActionInterpreter`.
    """
    def __init__(self, interpreter, output_style='file', parent_environ=None,
                 parent_variables=None, formatter=None, verbose=False,
                 env_sep_map=None):
        '''
        interpreter: string or `ActionInterpreter`
            the interpreter to use when executing rex actions
        output_style : str
            the style of the output string.  currently only 'file' and 'eval' are
            supported.  'file' is intended to be more human-readable, while 'eval' is
            intended to work in a shell `eval` statement. pratically, this means the
            former is separated by newlines, while the latter is separated by
            semi-colons.
        parent_environ: environment to execute the actions within. If None,
            defaults to the current environment.
        parent_variables: List of variables to append/prepend to, rather than
            overwriting on first reference. If this is set to True instead of a
            list, all variables are treated as parent variables.
        formatter: func or None
            function to use for formatting string values
        verbose : bool or list of str
            if True, causes commands to print additional feedback (using info()).
            can also be set to a list of strings matching command names to add
            verbosity to only those commands.
        '''
        self.interpreter = interpreter
        self.output_style = output_style
        self.verbose = verbose
        self.parent_environ = os.environ if parent_environ is None else parent_environ
        self.parent_variables = True if parent_variables is True \
            else set(parent_variables or [])
        self.environ = {}
        self.formatter = formatter or str
        self.actions = []

        # TODO: get rid of this feature
        self._env_sep_map = env_sep_map if env_sep_map is not None \
            else DEFAULT_ENV_SEP_MAP

    def get_action_methods(self):
        """
        return a list of methods on this class for executing actions.
        methods are return as a list of (name, func) tuples
        """
        return [(name, getattr(self, name)) for name,_ in Action.get_command_types()]

    def get_public_methods(self):
        """
        return a list of methods on this class which should be exposed in the rex
        API.
        """
        return self.get_action_methods() + [
            ('getenv', self.getenv),
            ('defined', self.defined),
            ('undefined', self.undefined)]

    def _env_sep(self, name):
        return self._env_sep_map.get(name, os.pathsep)

    def _is_verbose(self, command):
        if isinstance(self.verbose, (list, tuple)):
            return command in self.verbose
        else:
            return bool(self.verbose)

    def _format(self, value):
        """Format a string value."""
        # note that the default formatter is just str()
        if hasattr(value, '__iter__'):
            return type(value)(self.formatter(v) for v in value)
        else:
            return self.formatter(value)

    def _expand(self, value):
        value = expandvars(value, self.environ)
        value = expandvars(value, self.parent_environ)
        return os.path.expanduser(value)

    def get_output(self):
        return self.interpreter.get_output(self)

    # -- Commands

    def undefined(self, key):
        return (key not in self.environ) and (key not in self.parent_environ)

    def defined(self, key):
        return not self.undefined(key)

    def getenv(self, key):
        try:
            return self.environ.get(key, self.parent_environ[key])
        except KeyError:
            raise PkgCommandError("Referenced undefined environment variable: %s" % key)

    def setenv(self, key, value):
        # environment variables may be left unexpanded in values passed to interpreter functions
        unexpanded_value = self._format(value)
        # environment variables are expanded when storing in the environ dict
        expanded_value = self._expand(unexpanded_value)

        # TODO: check if value has already been set by another package
        self.actions.append(Setenv(key, unexpanded_value))
        self.environ[key] = expanded_value

        if self.interpreter.expand_env_vars:
            value = expanded_value
        else:
            value = unexpanded_value
        self.interpreter.setenv(key, value)

    def unsetenv(self, key):
        self.actions.append(Unsetenv(key))
        if key in self.environ:
            del self.environ[key]
        self.interpreter.unsetenv(key)

    def resetenv(self, key, value, friends=None):
        # environment variables may be left unexpanded in values passed to interpreter functions
        unexpanded_value = self._format(value)
        # environment variables are expanded when storing in the environ dict
        expanded_value = self._expand(unexpanded_value)

        self.actions.append(Resetenv(key, unexpanded_value, friends))
        self.environ[key] = expanded_value

        if self.interpreter.expand_env_vars:
            value = expanded_value
        else:
            value = unexpanded_value
        self.interpreter.resetenv(key, value)

    # we assume that ${THIS} is a valid variable ref in all shells
    @staticmethod
    def _keytoken(key):
        return "${%s}" % key

    def _pendenv(self, key, value, action, interpfunc, addfunc):
        # environment variables may be left unexpanded in values passed to interpreter functions
        unexpanded_value = self._format(value)
        # environment variables are expanded when storing in the environ dict
        expanded_value = self._expand(unexpanded_value)

        self.actions.append(action(key, unexpanded_value))

        if (key not in self.environ) and \
            ((self.parent_variables is True) or (key in self.parent_variables)):
            self.environ[key] = self.parent_environ.get(key, '')
            self.interpreter._saferefenv(key)

        if key in self.environ:
            parts = self.environ[key].split(self._env_sep(key))
            unexpanded_values = self._env_sep(key).join( \
                addfunc(unexpanded_value, [self._keytoken(key)]))
            expanded_values = self._env_sep(key).join(addfunc(expanded_value, parts))
            self.environ[key] = expanded_values
        else:
            self.environ[key] = expanded_value
            unexpanded_values = unexpanded_value

        try:
            if self.interpreter.expand_env_vars:
                value = expanded_value
            else:
                value = unexpanded_value
            interpfunc(key, value)
        except NotImplementedError:
            # if the interpreter does not implement prependenv/appendenv specifically,
            # we can simply call setenv with the computed value.  Currently only
            # python requires a special prependenv/appendenv
            if self.interpreter.expand_env_vars:
                value = expanded_values
            else:
                value = unexpanded_values
            self.interpreter.setenv(key, value)

    def prependenv(self, key, value):
        self._pendenv(key, value, Prependenv, self.interpreter.prependenv,
                      lambda x, y: [x] + y)

    def appendenv(self, key, value):
        self._pendenv(key, value, Appendenv, self.interpreter.appendenv,
                      lambda x, y: y + [x])

    def alias(self, key, value):
        value = self._format(value)
        self.actions.append(Alias(key, value))
        self.interpreter.alias(key, value)

    def info(self, value=''):
        value = self._format(value)
        self.actions.append(Info(value))
        self.interpreter.info(value)

    def error(self, value):
        value = self._format(value)
        self.actions.append(Error(value))
        self.interpreter.error(value)

    def command(self, value):
        value = self._format(value)
        self.actions.append(Command(value))
        self.interpreter.command(value)

    def comment(self, value):
        self.actions.append(Comment(value))
        self.interpreter.comment(value)

    def source(self, value):
        self.actions.append(Source(value))
        self.interpreter.source(value)

    def shebang(self):
        self.actions.append(Shebang())
        self.interpreter.shebang()


#===============================================================================
# Interpreters
#===============================================================================

class ActionInterpreter(object):
    """
    Abstract base class that provides callbacks for rex Actions.  This class
    should not be used directly. Its methods are called by the
    `ActionManager` in response to actions issued by user code written using
    the rex python API.

    Sub-classes should override the `get_output` method to return
    implementation-specific data structure.  For example, an interpreter for a
    shell language like bash would return a string of shell code.  An interpreter
    for an active python session might return a dictionary of the modified
    environment.

    Sub-classes can override the `expand_env_vars` class variable to instruct
    the `ActionManager` whether or not to expand the value of environment
    variables which reference other variables (e.g. "this-${THAT}").
    """
    expand_env_vars = False

    def get_output(self, manager):
        '''
        Returns any implementation specific data.

        Parameters
        ----------
        manager: ActionManager
            the manager of this interpreter
        '''
        raise NotImplementedError

    # --- commands

    def setenv(self, key, value):
        raise NotImplementedError

    def unsetenv(self, key):
        raise NotImplementedError

    def resetenv(self, key, value, friends=None):
        raise NotImplementedError

    def prependenv(self, key, value):
        '''
        this is optional, but if it is not implemented, you must implement setenv
        '''
        raise NotImplementedError

    def appendenv(self, key, value):
        '''
        this is optional, but if it is not implemented, you must implement setenv
        '''
        raise NotImplementedError

    def alias(self, key, value):
        raise NotImplementedError

    def info(self, value):
        raise NotImplementedError

    def error(self, value):
        raise NotImplementedError

    def command(self, value):
        raise NotImplementedError

    def comment(self, value):
        raise NotImplementedError

    def source(self, value):
        raise NotImplementedError

    def shebang(self):
        raise NotImplementedError

    # --- internal commands, not exposed to public rex API

    def _bind_interactive_rez(self):
        '''
        apply changes to the env needed to expose rez in an interactive shell,
        for eg prompt change, sourcing completion scripts etc. Do NOT add rez
        to PATH, this is done elsewhere.
        '''
        raise NotImplementedError

    def _saferefenv(self, key):
        '''
        make the var safe to reference, even if it does not yet exist. This is
        needed because of different behaviours in shells - eg, tcsh will fail
        on ref to undefined var, but sh will expand to the empty string.
        '''
        raise NotImplementedError


class Python(ActionInterpreter):
    '''Execute commands in the current python session'''
    expand_env_vars = True

    def __init__(self, target_environ=None, passive=False):
        '''
        target_environ: dict
            If target_environ is None or os.environ, interpreted actions are
            applied to the current python interpreter. Otherwise, changes are
            only applied to target_environ.

        passive: bool
            If True, commands that do not update the environment (such as info)
            are skipped.
        '''
        self.passive = passive
        self.manager = None
        if (target_environ is None) or (target_environ is os.environ):
            self.target_environ = os.environ
            self.update_session = True
        else:
            self.target_environ = target_environ
            self.update_session = False

    def set_manager(self, manager):
        self.manager = manager

    def get_output(self, manager):
        self.target_environ.update(manager.environ)
        return manager.environ

    def setenv(self, key, value):
        self._env_var_changed(key)

    def unsetenv(self, key):
        self._env_var_changed(key)

    def resetenv(self, key, value, friends=None):
        self._env_var_changed(key)

    def prependenv(self, key, value):
        if self.update_session:
            settings.env_var_changed(key)
            if key == 'PYTHONPATH':
                sys.path.insert(0, value)

    def appendenv(self, key, value):
        if self.update_session:
            settings.env_var_changed(key)
            if key == 'PYTHONPATH':
                sys.path.append(value)

    def info(self, value):
        if not self.passive:
            print value

    def error(self, value):
        if not self.passive:
            print >> sys.stderr, value

    def subprocess(self, args, **subproc_kwargs):
        if self.manager:
            self.target_environ.update(self.manager.environ)

        if not hasattr(args, '__iter__'):
            import shlex
            args = shlex.split(value)

        return subprocess.Popen(value, env=self.target_environ, **subproc_kwargs)

    def command(self, value):
        if self.passive:
            return
        try:
            p = self.subprocess(value)
            p.communicate()
        except Exception as e:
            cmd = shlex_join(value)
            raise Exception('Error executing command: %s\n%s' % (cmd, str(e)))

    def comment(self, value):
        pass

    def source(self, value):
        pass

    def alias(self, key, value):
        pass

    def _bind_interactive_rez(self):
        pass

    def _saferefenv(self, key):
        pass

    def shebang(self):
        pass

    def _env_var_changed(self, key):
        if self.update_session:
            settings.env_var_changed(key)


#===============================================================================
# Rex Execution Namespace
#===============================================================================

class NamespaceFormatter(Formatter):
    SINGLE_QUOTED_REGEX = re.compile(r"'[^']+'")
    ENV_VAR_REGEX       = re.compile(r"\${[A-Z_]+}")

    def __init__(self, namespace):
        Formatter.__init__(self)
        self.namespace = namespace

    def format(self, format_string, *args, **kwargs):
        toks = [(format_string, True)]

        for patt in (self.SINGLE_QUOTED_REGEX, self.ENV_VAR_REGEX):
            toks_ = []
            for (s,expand) in toks:
                if expand:
                    strs = patt.split(s)
                    patts = patt.findall(s)
                    for (s,p) in zip(strs, patts+['']):
                        toks_.append((s, True))
                        toks_.append((p, False))
                else:
                    toks_.append((s,expand))
            toks = toks_

        strs = []
        for (s,expand) in toks:
            if expand:
                try:
                    s_ = Formatter.format(self, s, *args, **kwargs)
                except KeyError:
                    s_ = s
                strs.append(s_)
            else:
                strs.append(s)
        return ''.join(strs)

    def get_value(self, key, args, kwds):
        """
        'get_value' is used to retrieve a given field value. The 'key' argument
        will be either an integer or a string. If it is an integer, it represents
        the index of the positional argument in 'args'; If it is a string, then
        it represents a named argument in 'kwargs'.
        """
        if isinstance(key, str):
            try:
                # Check explicitly passed arguments first
                return kwds[key]
            except KeyError:
                return self.namespace[key]
        else:
            return Formatter.get_value(self, key, args, kwds)


class MissingPackage(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.name)

    def __nonzero__(self):
        return False


class Packages(object):
    """
    Provides attribute-based lookups for `package.BasePackage` instances.

    If the package does not exist, the attribute value will be an empty string.
    This allows for attributes to be used to test the presence of a package and
    for non-existent packages to be used in string formatting without causing an
    error.
    """
    def __init__(self, pkg_list):
        for pkg in pkg_list:
            setattr(self, pkg.name, pkg)

    def __getattr__(self, attr):
        # For things like '__class__', for instance
        if attr.startswith('__') and attr.endswith('__'):
            try:
                self.__dict__[attr]
            except KeyError:
                raise AttributeError("'%s' object has no attribute "
                                     "'%s'" % (self.__class__.__name__,
                                               attr))
        return MissingPackage(attr)


#===============================================================================
# Environment Classes
#===============================================================================

class EnvironmentDict(UserDict.DictMixin):
    """
    Provides a mapping interface to `EnvironmentVariable` instances,
    which provide an object-oriented interface for recording environment
    variable manipulations.

    `__getitem__` is always guaranteed to return an `EnvironmentVariable`
    instance: it will not raise a KeyError.
    """
    def __init__(self, manager):
        """
        override_existing_lists : bool
            If True, the first call to append or prepend will override the
            value in `environ` and effectively act as a setenv operation.
            If False, pre-existing values will be appended/prepended to as usual.
        """
        self.manager = manager
        self._var_cache = {}

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, str(self._var_cache))

    def __getitem__(self, key):
        if key not in self._var_cache:
            self._var_cache[key] = EnvironmentVariable(key, self)
        return self._var_cache[key]

    def __setitem__(self, key, value):
        self[key].set(value)


class EnvironmentVariable(object):
    '''
    class representing an environment variable

    combined with EnvironmentDict class, records changes to the environment
    '''
    def __init__(self, name, environ_map):
        self._name = name
        self._environ_map = environ_map

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._name)

    @property
    def name(self):
        return self._name

    def prepend(self, value):
        self._environ_map.manager.prependenv(self.name, value)

    def append(self, value):
        self._environ_map.manager.appendenv(self.name, value)

    def reset(self, value, friends=None):
        self._environ_map.manager.resetenv(self.name, value, friends=friends)

    def set(self, value):
        self._environ_map.manager.setenv(self.name, value)

    def unset(self):
        self._environ_map.manager.unsetenv(self.name)

    # --- the following methods all require knowledge of the current environment

    def get(self):
        return self._environ_map.manager.getenv(self.name)

    def value(self):
        return self.get()

    def setdefault(self, value):
        '''set value if the variable does not yet exist'''
        if not self:
            self.set(value)

    def __str__(self):
        return self.value()

    def __nonzero__(self):
        return bool(self.value())

    def __eq__(self, value):
        if isinstance(value, EnvironmentVariable):
            value = value.value()
        return self.value() == value

    def __ne__(self, value):
        return not self == value


#===============================================================================
# Executors
#===============================================================================

class RexExecutor(object):
    """
    Runs an interpreter over code within the given namespace. You can also access
    namespaces and rex functions directly in the executor, like so:

    RexExecutor ex()
    ex.setenv('FOO', 'BAH')
    ex.env.FOO_SET = 1
    ex.alias('foo','foo -l')
    """
    def __init__(self, interpreter=None, globals_map=None, parent_environ=None,
                 parent_variables=None, output_style='file', bind_rez=True,
                 bind_syspaths=True, shebang=True, add_default_namespaces=True):
        """
        interpreter: `ActionInterpreter` or None
            the interpreter to use when executing rex actions. If None, creates
            a python interpreter with an empty target environment dict.
        globals_map : dict or None
            dictionary which comprises the main python namespace when rex code
            is executed (via the python `exec` statement). if None, defaults
            to empty dict.
        parent_environ: environment to execute the rex code within. If None, defaults
            to the current environment.
        parent_variables: List of variables to append/prepend to, rather than
            overwriting on first reference. If this is set to True instead of a
            list, all variables are treated as parent variables.
        bind_rez: bool
            if True, expose Rez cli tools in the target environment
        bind_syspaths: bool
            whether to append OS-specific paths to PATH when creating the environment
        shebang: bool
            if True, apply a shebang to the result.
        add_default_namespaces: bool
            whether to add default namespaces such as 'machine'.
        """
        self.globals = globals_map or {}
        self.formatter = NamespaceFormatter(self.globals)
        self.bind('format', self.expand)

        if interpreter is None:
            interpreter = Python(target_environ={})

        self.manager = ActionManager(interpreter,
                                     formatter=self.expand,
                                     output_style=output_style,
                                     parent_environ=parent_environ,
                                     parent_variables=parent_variables)

        if isinstance(interpreter, Python):
            interpreter.set_manager(self.manager)

        if shebang:
            self.manager.shebang()

        self.environ = EnvironmentDict(self.manager)
        self.bind('env', AttrDictWrapper(self.environ))

        # expose Rez/system in PATH
        paths = []
        if bind_rez:
            paths = [get_script_path()]
        # TODO make this configurable. Will probably be better to append syspaths at the end
        if bind_syspaths:
            paths += self._get_syspaths()
        if paths:
            self.environ["PATH"] = os.pathsep.join(paths)

        for cmd,func in self.manager.get_public_methods():
            self.bind(cmd, func)

        if add_default_namespaces:
            self.bind('machine', system)
            self.bind('user', getpass.getuser())

    @property
    def interpreter(self):
        return self.manager.interpreter

    def __getattr__(self, attr):
        """
        Allows for access such as: self.setenv('FOO','bah')
        """
        return self.globals[attr] if attr in self.globals \
            else getattr(super(RexExecutor,self), attr)

    def bind(self, name, obj):
        """
        Binds an object to the execution context.
        """
        self.globals[name] = obj

    def update_env(self, d):
        """
        Update the environment in the execution context.
        """
        self.environ.update(d)

    def execute_code(self, code, filename=None):
        """
        Execute code within the execution context.
        """
        filename = filename or 'REX'
        try:
            pyc = compile(code, filename, 'exec')
            exec pyc in self.globals
        except Exception as e:
            # trim trace down to only what's interesting
            import traceback
            frames = traceback.extract_tb(sys.exc_traceback)
            while frames and frames[0][0] != filename:
                frames = frames[1:]
            while frames and __file__.startswith(frames[-1][0]):
                frames = frames[:-1]
            stack = ''.join(traceback.format_list(frames)).strip()
            raise Exception("Error in rex code: %s\n%s" % (str(e), stack))

    def execute_function(self, func, *nargs, **kwargs):
        """
        Execute a function object within the execution context.
        @returns The result of the function call.
        """
        # makes a copy of the func
        import types
        fn = types.FunctionType(func.func_code,
                                func.func_globals.copy(),
                                name=func.func_name,
                                argdefs=func.func_defaults,
                                closure=func.func_closure)
        fn.func_globals.update(self.globals)
        return fn(*nargs, **kwargs)

    def get_output(self):
        """
        Returns the result of all previous calls to execute_code.
        """
        return self.manager.get_output()

    def expand(self, value):
        return self.formatter.format(str(value))

    def _get_syspaths(self):
        from rez.shells import Shell, create_shell
        sh = self.interpreter if isinstance(self.interpreter, Shell) \
            else create_shell()
        return sh.get_syspaths()




"""
class RexResolveExecutor(RexExecutor):
    def __init__(self, interpreter, resolve_result, globals_map=None,
                 environ=None, sys_path_append=True):
        super(RexResolveExecutor,self).__init__(interpreter,
                                                globals_map=globals_map,
                                                environ=environ,
                                                sys_path_append=sys_path_append,
                                                add_default_namespaces=True)
        self.resolve = resolve_result
        if add_default_namespaces:
            self.bind('resolve', Packages(self.resolve.package_resolves))
            self.bind('request', Packages(self.resolve.package_requests))

    def execute_package(self, pkg_res, commands):
        prefix = "REZ_" + pkg_res.name.upper()
        self.environ[prefix + "_VERSION"] = pkg_res.version
        self.environ[prefix + "_BASE"] = pkg_res.base
        self.environ[prefix + "_ROOT"] = pkg_res.root

        self.bind('this', pkg_res)
        self.bind('root', pkg_res.root)
        self.bind('base', pkg_res.base)
        self.bind('version', pkg_res.version)

        # new style package.yaml:
        if isinstance(commands, basestring):
            # compile to get tracebacks with line numbers and file.
            code = compile(commands, pkg_res.metafile, 'exec')
            try:
                exec code in self.globals
            except Exception, err:
                import traceback
                raise PkgCommandError("%s (%s):\n %s" % (pkg_res.short_name(),
                                                         pkg_res.metafile,
                                                         traceback.format_exc()))
        # python function from package.py:
        elif inspect.isfunction(commands):
            commands.func_globals.update(self.globals)
            try:
                commands()
            except Exception, err:
                import traceback
                raise PkgCommandError("%s (%s):\n %s" % (pkg_res.short_name(),
                                                         pkg_res.metafile,
                                                         traceback.format_exc()))
        # old style package.yaml:
        elif isinstance(commands, list):
            if settings.warn_old_commands:
                print_warning_once("%s is using old-style commands."
                                   % pkg_res.short_name())
            expansions = []
            expansions.append(("!VERSION!", str(pkg_res.version)))
            if len(pkg_res.version.parts):
                expansions.append(("!MAJOR_VERSION!", str(pkg_res.version.major)))
                if len(pkg_res.version.parts) > 1:
                    expansions.append(("!MINOR_VERSION!", str(pkg_res.version.minor)))
            expansions.append(("!BASE!", str(pkg_res.base)))
            expansions.append(("!ROOT!", str(pkg_res.root)))
            expansions.append(("!USER!", os.getenv("USER", "UNKNOWN_USER")))

            for cmd in commands:
                for find, replace in expansions:
                    cmd = cmd.replace(find, replace)
                # convert to new-style
                self._parse_export_command(cmd)

    def execute_packages(self, metadata_commands_section='commands'):
        # build the environment commands
        # the environment dictionary to be passed during execution of python code.
        #self = self._setup_execution_namespace()

        def stringify(pkg_list):
            return ' '.join([x.short_name() for x in pkg_list])

        self.environ["REZ_USED"] = module_root_path
        self.environ["REZ_PREV_REQUEST"] = "$REZ_REQUEST"
        self.environ["REZ_REQUEST"] = stringify(self.resolve.package_requests)
        self.environ["REZ_RAW_REQUEST"] = stringify(self.resolve.raw_package_requests)
        self.environ["REZ_RESOLVE"] = stringify(self.resolve.package_resolves)
        self.environ["REZ_RESOLVE_MODE"] = self.resolve.resolve_mode
        self.environ["REZ_FAILED_ATTEMPTS"] = self.resolve.failed_attempts
        self.environ["REZ_REQUEST_TIME"] = self.resolve.request_timestamp

        # TODO remove this and have Rez create a proper rez package for itself
        #self.environ["PYTHONPATH"] = os.path.join(module_root_path, 'python')

        # TODO improve mgmt of system paths, make more configurable
        # we need to inject system paths here. They're not there already because they can't be cached
        sys_paths = [os.path.join(module_root_path, "bin")]
        if self.sys_path_append:
            sys_paths += system.executable_paths
        self.environ["PATH"] = os.pathsep.join(sys_paths)

        self.environ["REZ_PACKAGES_PATH"] = '$REZ_PACKAGES_PATH'

        self.manager.comment("-" * 30)
        self.manager.comment("START of package commands")
        self.manager.comment("-" * 30)

        set_vars = {}

        for pkg_res in self.resolve.package_resolves:
#             # swap the command self.manager so we can isolate commands for this package
#             self.manager = rex.CommandRecorder()
#             self.set_command_recorder(self.manager)
            self.manager.comment("")
            self.manager.comment("Commands from package %s" % pkg_res.name)

            self.execute_package(pkg_res, pkg_res.metadata[metadata_commands_section])

#             pkg_res.commands = self.manager.get_commands()
# 
#             # FIXME: getting an error with an append, which should not happen
#             # check for variables set by multiple packages
#             for cmd in pkg_res.commands:
#                 if cmd.name == 'setenv':
#                     if set_vars.get(cmd.key, None) not in [None, pkg_res.name]:
#                         raise PkgCommandError("Package '%s' overwrote the value '%s' set by "
#                                               "package '%s'" % (pkg_res.name, cmd.key,
#                                                               set_vars[cmd.key]))
#                     set_vars[cmd.key] = pkg_res.name
# 
#                 elif cmd.name == 'resetenv':
#                     prev_pkg_name = set_vars.get(cmd.key, None)
#                     if cmd.friends:
#                         if prev_pkg_name not in cmd.friends + [None, pkg_res.name]:
#                             raise PkgCommandError("Package '%s' overwrote the value '%s' set by "
#                                                   "package '%s', and is not in the list "
#                                                   "of friends %s" % (pkg_res.name, cmd.key,
#                                                                      prev_pkg_name, cmd.friends))
#                     set_vars[cmd.key] = pkg_res.name

        self.manager.comment("-" * 30)
        self.manager.comment("END of package commands")
        self.manager.comment("-" * 30)

        # TODO: add in execution time?
        self.manager.setenv('REZ_TIME_TO_RESOLVE', str(self.resolve.resolve_time))

        return self.manager.get_output()

    def add_meta_vars(self, meta_vars, shallow_meta_vars):
        "
        meta_vars: list of str
                each string is a key whos value will be saved into an
                env-var named REZ_META_<KEY> (lists are comma-separated).
        shallow_meta_vars: list of str
                same as meta-vars, but only the values from those packages directly
                requested are baked into the env var REZ_META_SHALLOW_<KEY>.
        "
        # add meta env vars
        pkg_req_fam_set = set([x.name for x in self.package_requests if not x.is_anti()])
        meta_envvars = {}
        shallow_meta_envvars = {}
        for pkg_res in self.package_resolves:
            def _add_meta_vars(mvars, target):
                for key in mvars:
                    if key in pkg_res.metadata:
                        val = pkg_res.metadata[key]
                        if isinstance(val, list):
                            val = ','.join(val)
                        if key not in target:
                            target[key] = []
                        target[key].append(pkg_res.name + ':' + val)

            if meta_vars:
                _add_meta_vars(meta_vars, meta_envvars)

            if shallow_meta_vars and pkg_res.name in pkg_req_fam_set:
                _add_meta_vars(shallow_meta_vars, shallow_meta_envvars)

        for k, v in meta_envvars.iteritems():
            self.manager.setenv('REZ_META_' + k.upper(), ' '.join(v))
        for k, v in shallow_meta_envvars.iteritems():
            self.manager.setenv('REZ_META_SHALLOW_' + k.upper(), ' '.join(v))

    def _parse_export_command(self, cmd):
        if isinstance(cmd, list):
            cmd = cmd[0]
            pkgname = cmd[1]
        else:
            cmd = cmd
            pkgname = None

        if cmd.startswith('export '):
            var, value = cmd.split(' ', 1)[1].split('=', 1)
            value = value.strip('"')
            # get an EnvironmentVariable instance
            var_obj = self.environ[var]
            parts = value.split(PARSE_EXPORT_COMMAND_ENV_SEP_MAP.get(var, os.pathsep))
            if len(parts) > 1:
                orig_parts = parts
                parts = [x for x in parts if x]
                if '$' + var in parts:
                    # append / prepend
                    index = parts.index('$' + var)
                    if index == 0:
                        # APPEND   X=$X:foo
                        for part in parts[1:]:
                            var_obj.append(part)
                    elif index == len(parts) - 1:
                        # PREPEND  X=foo:$X
                        # loop in reverse order
                        for part in parts[-2::-1]:
                            var_obj.prepend(part)
                    else:
                        raise PkgCommandError("%s: self-referencing used in middle "
                                              "of list: %s" % (pkgname, value))

                else:
                    if len(parts) == 1:
                        # use blank values in list to determine if the original
                        # operation was prepend or append
                        assert len(orig_parts) == 2
                        if orig_parts[0] == '':
                            var_obj.append(parts[0])
                        elif orig_parts[1] == '':
                            var_obj.prepend(parts[0])
                        else:
                            print "only one value", parts
                    else:
                        var_obj.set(os.pathsep.join(parts))
            else:
                var_obj.set(value)
        elif cmd.startswith('#'):
            self.manager.comment(cmd[1:].lstrip())
        elif cmd.startswith('alias '):
            match = re.search("alias (?P<key>.*)=(?P<value>.*)", cmd)
            key = match.groupdict()['key'].strip()
            value = match.groupdict()['value'].strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            self.manager.alias(key, value)
        else:
            # assume we can execute this as a straight command
            self.manager.command(cmd)
"""
