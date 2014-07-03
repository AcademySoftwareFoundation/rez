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
from rez.config import config
from rez.exceptions import RexError, RexUndefinedVariableError
from rez.util import print_warning_once, AttrDictWrapper, shlex_join, \
    get_script_path, which


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
        unexpanded_key = self._format(key)
        expanded_key = self._expand(unexpanded_key)
        return (expanded_key not in self.environ
                and expanded_key not in self.parent_environ)

    def defined(self, key):
        return not self.undefined(key)

    def getenv(self, key):
        unexpanded_key = self._format(key)
        expanded_key = self._expand(unexpanded_key)
        try:
            return self.environ[expanded_key] if expanded_key in self.environ \
                else self.parent_environ[expanded_key]
        except KeyError:
            raise RexUndefinedVariableError(
                "Referenced undefined environment variable: %s" % expanded_key)

    def setenv(self, key, value):
        unexpanded_key = self._format(key)
        unexpanded_value = self._format(value)
        expanded_key = self._expand(unexpanded_key)
        expanded_value = self._expand(unexpanded_value)

        # TODO: check if value has already been set by another package
        self.actions.append(Setenv(unexpanded_key, unexpanded_value))
        self.environ[expanded_key] = expanded_value

        if self.interpreter.expand_env_vars:
            key, value = expanded_key, expanded_value
        else:
            key, value = unexpanded_key, unexpanded_value
        self.interpreter.setenv(key, value)

    def unsetenv(self, key):
        unexpanded_key = self._format(key)
        expanded_key = self._expand(unexpanded_key)
        self.actions.append(Unsetenv(unexpanded_key))
        if expanded_key in self.environ:
            del self.environ[expanded_key]
        if self.interpreter.expand_env_vars:
            key = expanded_key
        else:
            key = unexpanded_key
        self.interpreter.unsetenv(key)

    def resetenv(self, key, value, friends=None):
        unexpanded_key = self._format(key)
        unexpanded_value = self._format(value)
        expanded_key = self._expand(unexpanded_key)
        expanded_value = self._expand(unexpanded_value)

        self.actions.append(Resetenv(unexpanded_key, unexpanded_value,
                                     friends))
        self.environ[expanded_key] = expanded_value

        if self.interpreter.expand_env_vars:
            key, value = expanded_key, expanded_value
        else:
            key, value = unexpanded_key, unexpanded_value
        self.interpreter.resetenv(key, value)

    # we assume that ${THIS} is a valid variable ref in all shells
    @staticmethod
    def _keytoken(key):
        return "${%s}" % key

    def _pendenv(self, key, value, action, interpfunc, addfunc):
        unexpanded_key = self._format(key)
        unexpanded_value = self._format(value)
        expanded_key = self._expand(unexpanded_key)
        expanded_value = self._expand(unexpanded_value)

        # expose env-vars from parent env if explicitly told to do so
        if (expanded_key not in self.environ) and \
            ((self.parent_variables is True) or (expanded_key in self.parent_variables)):
            self.environ[expanded_key] = self.parent_environ.get(expanded_key, '')
            if self.interpreter.expand_env_vars:
                key_ = expanded_key
            else:
                key_ = unexpanded_key
            self.interpreter._saferefenv(key_)

        # *pend or setenv depending on whether this is first reference to the var
        if expanded_key in self.environ:
            self.actions.append(action(unexpanded_key, unexpanded_value))
            parts = self.environ[expanded_key].split(self._env_sep(expanded_key))
            unexpanded_values = self._env_sep(expanded_key).join( \
                addfunc(unexpanded_value, [self._keytoken(expanded_key)]))
            expanded_values = self._env_sep(expanded_key).join(addfunc(expanded_value, parts))
            self.environ[expanded_key] = expanded_values
        else:
            self.actions.append(Setenv(unexpanded_key, unexpanded_value))
            self.environ[expanded_key] = expanded_value
            expanded_values = expanded_value
            unexpanded_values = unexpanded_value
            interpfunc = None

        applied = False
        if interpfunc:
            if self.interpreter.expand_env_vars:
                key, value = expanded_key, expanded_value
            else:
                key, value = unexpanded_key, unexpanded_value
            try:
                interpfunc(key, value)
                applied = True
            except NotImplementedError:
                pass

        if not applied:
            if self.interpreter.expand_env_vars:
                key, value = expanded_key, expanded_values
            else:
                key, value = unexpanded_key, unexpanded_values
            self.interpreter.setenv(key, value)

    def prependenv(self, key, value):
        self._pendenv(key, value, Prependenv, self.interpreter.prependenv,
                      lambda x, y: [x] + y)

    def appendenv(self, key, value):
        self._pendenv(key, value, Appendenv, self.interpreter.appendenv,
                      lambda x, y: y + [x])

    def alias(self, key, value):
        key = self._format(key)
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
        value = self._format(value)
        self.actions.append(Comment(value))
        self.interpreter.comment(value)

    def source(self, value):
        value = self._format(value)
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
        """Returns any implementation specific data.

        Args:
            manager: ActionManager the manager of this interpreter
        """
        raise NotImplementedError

    # --- commands

    def setenv(self, key, value):
        raise NotImplementedError

    def unsetenv(self, key):
        raise NotImplementedError

    def resetenv(self, key, value, friends=None):
        raise NotImplementedError

    def prependenv(self, key, value):
        """This is optional, but if it is not implemented, you must
        implement setenv."""
        raise NotImplementedError

    def appendenv(self, key, value):
        """This is optional, but if it is not implemented, you must
        implement setenv."""
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
        if self.update_session:
            if key == 'PYTHONPATH':
                sys.path = value.split(os.pathsep)

    def unsetenv(self, key):
        pass

    def resetenv(self, key, value, friends=None):
        pass

    def prependenv(self, key, value):
        if self.update_session:
            if key == 'PYTHONPATH':
                sys.path.insert(0, value)

    def appendenv(self, key, value):
        if self.update_session:
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
            args = shlex.split(args)

        return subprocess.Popen(args, env=self.target_environ,
                                **subproc_kwargs)

    def command(self, value):
        if self.passive:
            return
        try:
            p = self.subprocess(value)
            p.communicate()
        except Exception as e:
            cmd = shlex_join(value)
            raise RexError('Error executing command: %s\n%s' % (cmd, str(e)))

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


#===============================================================================
# Rex Execution Namespace
#===============================================================================
class NamespaceFormatter(Formatter):
    ENV_VAR_REGEX = re.compile("\${(?P<var>.+?)}")

    def __init__(self, namespace):
        Formatter.__init__(self)
        self.namespace = namespace

    def format(self, format_string, *args, **kwargs):
        def escape_envvar(matchobj):
            return "${{%s}}" % (matchobj.group("var"))

        escaped_format_string = re.sub(self.ENV_VAR_REGEX, escape_envvar, format_string)
        return Formatter.format(self, escaped_format_string, *args, **kwargs)

    def get_value(self, key, args, kwds):
        if isinstance(key, str):
            if key:
                try:
                    # Check explicitly passed arguments first
                    return kwds[key]
                except KeyError:
                    return self.namespace[key]
            else:
                raise ValueError("zero length field name in format")
        else:
            return Formatter.get_value(self, key, args, kwds)


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
        """Creates an `EnvironmentDict`.

        Args:
            override_existing_lists (bool): If True, the first call to append
                or prepend will override the value in `environ` and effectively
                act as a setenv operation. If False, pre-existing values will
                be appended/prepended to as usual.
        """
        self.manager = manager
        self._var_cache = dict((k, EnvironmentVariable(k, self))
                               for k in manager.parent_environ.iterkeys())

    def keys(self):
        return self._var_cache.keys()

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, str(self._var_cache))

    def __getitem__(self, key):
        if key not in self._var_cache:
            self._var_cache[key] = EnvironmentVariable(key, self)
        return self._var_cache[key]

    def __setitem__(self, key, value):
        self[key].set(value)

    def __contains__(self, key):
        return (key in self._var_cache)


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
                 shebang=True, add_default_namespaces=True):
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

        if bind_rez:
            script_path = get_script_path()
            if not script_path:
                binary = which("rezolve")
                if binary:
                    script_path = os.path.dirname(binary)
            if script_path:
                self.environ["PATH"] = script_path

        for cmd, func in self.manager.get_public_methods():
            self.bind(cmd, func)

        if add_default_namespaces:
            self.bind('machine', system)
            self.bind('user', getpass.getuser())

    @property
    def interpreter(self):
        return self.manager.interpreter

    @property
    def actions(self):
        """List of Action objects that will be executed."""
        return self.manager.actions

    def __getattr__(self, attr):
        """Allows for access such as: self.setenv('FOO','bah')."""
        return self.globals[attr] if attr in self.globals \
            else getattr(super(RexExecutor, self), attr)

    def bind(self, name, obj):
        """Binds an object to the execution context."""
        self.globals[name] = obj

    def append_system_paths(self):
        """Append system paths to $PATH."""
        from rez.shells import Shell, create_shell
        sh = self.interpreter if isinstance(self.interpreter, Shell) \
            else create_shell()

        paths = sh.get_syspaths()
        paths_str = os.pathsep.join(paths)
        self.env.PATH.append(paths_str)

    def execute_code(self, code, filename=None):
        """Execute code within the execution context."""
        filename = filename or "<string>"
        error_class = Exception if config.catch_rex_errors else None
        try:
            pyc = compile(code, filename, 'exec')
            exec pyc in self.globals
        except error_class as e:
            # trim trace down to only what's interesting
            import traceback
            frames = traceback.extract_tb(sys.exc_traceback)
            frames = [x for x in frames if x[0] == filename]
            self._patch_frames(frames, code)
            self._raise_rex_error(frames, e)

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
        error_class = Exception if config.catch_rex_errors else None

        try:
            return fn(*nargs, **kwargs)
        except error_class as e:
            # trim trace down to only what's interesting
            import traceback
            frames = traceback.extract_tb(sys.exc_traceback)

            filepath = inspect.getfile(func)
            if os.path.exists(filepath):
                frames = [x for x in frames if x[0] == filepath]
            self._raise_rex_error(frames, e)

    def get_output(self):
        """Returns the result of all previous calls to execute_code."""
        return self.manager.get_output()

    def expand(self, value):
        return self.formatter.format(str(value))

    def _patch_frames(self, frames, code, codefile="<string>"):
        """Patch traceback's frame objects to add lines of code from `code`
        where appropriate.
        """
        loc = code.split('\n')
        for i, frame in enumerate(frames):
            filename, lineno, name, line = frame
            if filename == codefile and line is None:
                try:
                    line = loc[lineno-1].strip()
                    frames[i] = (filename, lineno, "<rex commands>", line)
                except:
                    pass

    def _raise_rex_error(self, frames, e):
        import traceback
        stack = ''.join(traceback.format_list(frames)).strip()
        if isinstance(e, RexError):
            raise type(e)("%s\n%s" % (str(e), stack))
        else:
            raise RexError("Error in rex code: %s - %s\n%s"
                           % (e.__class__.__name__, str(e), stack))
