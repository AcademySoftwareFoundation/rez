import os
import subprocess
import sys
import posixpath
import ntpath
from string import Formatter, Template
import re
import UserDict
#import textwrap
import pipes
import inspect
import time
from rez import module_root_path
from rez.settings import settings
from rez.system import system
import rez.util as util
from rez.util import print_warning_once
from rez.exceptions import PkgCommandError

ATTR_REGEX_STR = r"([_a-z][_a-z0-9]*)([._a-z][_a-z0-9]*)*"
FUNC_REGEX_STR = r"\([a-z0-9_\-.]*\)"

DEFAULT_ENV_SEP_MAP = {'CMAKE_MODULE_PATH': ';'}

EnvExpand = Template

class NamespaceFormatter(Formatter):
    def __init__(self, namespace):
        Formatter.__init__(self)
        self.namespace = namespace

    def get_value(self, key, args, kwds):
        """
        'get_value' is used to retrieve a given field value.  The 'key' argument
        will be either an integer or a string.  If it is an integer, it represents
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
            return Formatter.get_value(key, args, kwds)

#===============================================================================
# Path Utils
#===============================================================================

if sys.version_info < (2, 7, 4):
    from rez.contrib._joinrealpath import _joinrealpath
else:
    from os.path import _joinrealpath

def _abspath(root, value):
    # not all variables are paths: only absolutize if it looks like a relative path
    if root and \
        (value.startswith('./') or
         ('/' in value and not (posixpath.isabs(value) or ntpath.isabs(value)))):
        value = os.path.join(root, value)
    return value

def _split_env(value):
    return value.split(os.pathsep)

def _join_env(values):
    return os.pathsep.join(values)

def _realpath(value):
    # cannot call os.path.realpath because it always calls os.path.abspath
    # output:
    seen = {}
    newpath, ok = _joinrealpath('', value, seen)
    # only call abspath if a link was resolved:
    if seen:
        return os.path.abspath(newpath)
    return newpath

def _nativepath(path):
    return os.path.join(path.split('/'))

def _ntpath(path):
    return ntpath.sep.join(path.split(posixpath.sep))

def _posixpath(path):
    return posixpath.sep.join(path.split(ntpath.sep))


#===============================================================================
# Commands
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

class ActionManager(object):
    """
    Handles the execution book-keeping.  Tracks env variable values, and
    triggers the callbacks of the `ActionInterpreter`.
    """
    def __init__(self, interpreter, output_style='file', parent_environ=None,
                 formatter=None, verbose=False, env_sep_map=None):
        '''
        interpreter: string or `ActionInterpreter`
            the interpreter to use when executing rex actions
        output_style : str
            the style of the output string.  currently only 'file' and 'eval' are
            supported.  'file' is intended to be more human-readable, while 'eval' is
            intended to work in a shell `eval` statement. pratically, this means the
            former is separated by newlines, while the latter is separated by
            semi-colons.
        formatter: func or None
            function to use for formatting string values
        verbose : bool or list of str
            if True, causes commands to print additional feedback (using info()).
            can also be set to a list of strings matching command names to add
            verbosity to only those commands.
        '''
        if isinstance(interpreter, basestring):
            self.interpreter = get_command_interpreter(interpreter)()
        else:
            self.interpreter = interpreter
        self.output_style = output_style
        self.verbose = verbose
        self.parent_environ = parent_environ if parent_environ else {}
        self.environ = {}
        self.formatter = formatter if formatter else str
        self.actions = []

        # TODO: get rid of this feature
        self._env_sep_map = env_sep_map if env_sep_map is not None else {}

    def get_action_methods(self):
        """
        return a list of methods on this class for executing actions.
        methods are return as a list of (name, func) tuples
        """
        return [(name, getattr(self, name)) for name, _ in Action.get_command_types()]

    def get_public_methods(self):
        """
        return a list of methods on this class which should be exposed in the rex
        API.
        """
        return self.get_action_methods() + [('getenv', self.getenv)]

    def _env_sep(self, name):
        return self._env_sep_map.get(name, os.pathsep)

    def _is_verbose(self, command):
        if isinstance(self.verbose, (list, tuple)):
            return command in self.verbose
        else:
            return bool(self.verbose)

    def _format(self, value):
        """
        format a string value
        """
        # note that the default formatter is just str()
        if isinstance(value, (list, tuple)):
            return [self.formatter(v) for v in value]
        else:
            return self.formatter(value)

    def _expand(self, value):
        return os.path.expanduser(os.path.expandvars(value))

    def get_output(self):
        return self.interpreter.get_output(self)

    # -- Commands

    def getenv(self, key):
        try:
            return self.environ[key]
        except KeyError:
            try:
                return self.parent_environ[key]
            except KeyError:
                raise PkgCommandError("Referenced undefined environment variable: %s" % key)

    def setenv(self, key, value):
        # environment variables are left unexpanded in values passed to the interpreter functions
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
        self.environ.pop(key)
        self.interpreter.unsetenv(key)

    def resetenv(self, key, value, friends=None):
        # environment variables are left unexpanded in values passed to the interpreter functions
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

    def _pendenv(self, key, value, action, interpfunc, addfunc):
        # environment variables are left unexpanded in values passed to the interpreter functions
        unexpanded_value = self._format(value)
        # environment variables are expanded when storing in the environ dict
        expanded_value = self._expand(unexpanded_value)

        self.actions.append(action(key, unexpanded_value))

        if key in self.environ:
            parts = self.environ[key].split(self._env_sep(key))
            unexpanded_values = self._env_sep(key).join(addfunc(unexpanded_value, ['$' + key]))
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

#===============================================================================
# Interpreters
#===============================================================================

class ActionInterpreter(object):
    """
    Abstract base class that provides callbacks for rex Actions.  This class
    should not be used directly. Its callbacks are triggered by the
    `ActionManager` in response to actions issues by user code written using
    the rex python API.

    Sub-classes should override the `get_output` method to return
    implementation-specific data structure.  For example, an interpreter for a
    shell language like bash would return a string of shell code.  An interpreter
    for an active python session might return a dictionary of the modified
    environment.
    """
    expand_env_vars = False
#     def _execute(self, command_list):
#         lines = []
#         header = self.begin()
#         if header:
#             lines.append(header)
# 
#         for cmd in command_list:
#             func = getattr(self, cmd.name)
#             pre_func = getattr(cmd, 'pre_exec', None)
#             if pre_func:
#                 pre_func(self)
#             if self._is_verbose(cmd.name):
#                 self.info("running %s: %s" % (cmd.name, ' '.join(str(x) for x in cmd.args)))
#             result = func(*cmd.args)
#             post_func = getattr(cmd, 'post_exec', None)
#             if post_func:
#                 result = post_func(self, result)
#             if result is not None:
#                 lines.append(result)
#         footer = self.end()
#         if footer:
#             lines.append(footer)
#         line_sep = '\n' if self.output_style == 'file' else ';'
#         script = line_sep.join(lines)
#         script += line_sep
#         return script

    def get_output(self, manager):
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

class Shell(ActionInterpreter):
    def __init__(self):
        self._lines = []

    def _addline(self, line):
        self._lines.append(line)

    def get_output(self, manager):
        line_sep = '\n' if manager.output_style == 'file' else ';'
        script = line_sep.join(self._lines)
        script += line_sep
        return script

class SH(Shell):
    # This caused a silent abort during rez-env. very bad.
    # def begin(self):
    #     return '# stop on error:\nset -e'

    def setenv(self, key, value):
        self._addline('export %s="%s"' % (key, value))

    def unsetenv(self, key):
        self._addline("unset %s" % (key,))

    def resetenv(self, key, value, friends=None):
        self._addline(self.setenv(key, value))

#     def prependenv(self, key, value):
#         self._addline('export %(key)s="%(value)s%(sep)s$%(key)s"' % dict(
#             key=key,
#             value=value,
#             sep=self._env_sep(key)))

        # if key in self._environ:
        #     return 'export {key}="{value}{sep}${key}"'.format(key=key,
        #                                                       sep=self._env_sep(key),
        #                                                       value=value)
        # if not self._respect_parent_env:
        #     return self.setenv(key, value)
        # if self.output_style == 'file':
        #     return textwrap.dedent('''\
        #         if [[ ${key} ]]; then
        #             export {key}="{value}"
        #         else
        #             export {key}="{value}{sep}${key}"
        #         fi'''.format(key=key,
        #                      sep=self._env_sep(key),
        #                      value=value))
        # else:
        #     return "[[ {key} ]] && export {key}={value}{sep}${key} || export {key}={value}".format(key=key,
        #                                                                                            sep=self._env_sep(key),
        #                                                                                            value=value)

#     def appendenv(self, key, value):
#         self._addline('export %(key)s="$%(key)s%(sep)s%(value)s"' % dict(
#             key=key,
#             value=value,
#             sep=self._env_sep(key)))

        # if key in self._environ:
        #     return 'export {key}="${key}{sep}{value}"'.format(key=key,
        #                                                       sep=self._env_sep(key),
        #                                                       value=value)
        # if not self._respect_parent_env:
        #     return self.setenv(key, value)
        # if self.output_style == 'file':
        #     return textwrap.dedent('''\
        #         if [[ ${key} ]]; then
        #             export {key}="{value}"
        #         else
        #             export {key}="${key}{sep}{value}"
        #         fi'''.format(key=key,
        #                      sep=self._env_sep(key),
        #                      value=value))
        # else:
        #     return "[[ {key} ]] && export {key}=${key}{sep}{value} || export {key}={value}".format(key=key,
        #                                                                                            sep=self._env_sep(key),
        #                                                                                            value=value)

    def alias(self, key, value):
        # bash aliases don't export to subshells; so instead define a function,
        # then export that function
        self._addline("{key}() {{ {value}; }};export -f {key};".format(key=key,
                                                              value=value))

    def info(self, value):
        # TODO: handle newlines
        self._addline('echo "%s"' % value)

    def error(self, value):
        # TODO: handle newlines
        self._addline('echo "%s" 1>&2' % value)

    def command(self, value):
        def quote(s):
            if '$' not in s:
                return pipes.quote(s)
            return s

        if isinstance(value, (list, tuple)):
            value = ' '.join(quote(x) for x in value)
        self._addline(str(value))

    def comment(self, value):
        # TODO: handle newlines
        self._addline("# %s" % value)

    def source(self, value):
        self._addline('source "%s"' % value)

class CSH(SH):
    def setenv(self, key, value):
        # I don't think this is needed any more 
#         if re.search("^\${?[A-Z_]+}?$", value):
#             return """if ($?{value_}) then
#     setenv {key} "{value}"
# else
#     setenv {key}
# endif
# """.format(key=key, sep=self._env_sep(key), value=value, value_=value[1:])
#         else:
        self._addline('setenv %s "%s"' % (key, value))

    def unsetenv(self, key):
        self._addline("unsetenv %s" % (key,))

    def resetenv(self, key, value, friends=None):
        self.setenv(key, value)

#     def prependenv(self, key, value):
#         self._addline('setenv {key} {value}{sep}${{{key}}}'.format(key=key,
#                                                                    sep=self._env_sep(key),
#                                                                    value=value))

#         if key in self._environ:
#             return 'setenv {key}="{value}{sep}${key}"'.format(key=key,
#                                                               sep=self._env_sep(key),
#                                                               value=value)
#         if not self._respect_parent_env:
#             return self.setenv(key, value)
#         return textwrap.dedent('''\
#             if ( ! $?{key} ) then
#                 setenv {key} "{value}"
#             else
#                 setenv {key} "{value}{sep}${key}"
#             endif'''.format(key=key,
#                             sep=self._env_sep(key),
#                             value=value))

#     def appendenv(self, key, value):
#         self._addline('setenv {key} ${{{key}}}{sep}{value}'.format(key=key,
#                                                                    sep=self._env_sep(key),
#                                                                    value=value)

#         if key in self._environ:
#             return 'setenv {key}="${key}{sep}{value}"'.format(key=key,
#                                                               sep=self._env_sep(key),
#                                                               value=value)
#         if not self._respect_parent_env:
#             return self.setenv(key, value)
#         return textwrap.dedent('''\
#             if ( ! $?{key} ) then
#                 setenv {key} "{value}"
#             else
#                 setenv {key} "${key}{sep}{value}"
#             endif'''.format(key=key,
#                             sep=self._env_sep(key),
#                             value=value))

    def alias(self, key, value):
        return "alias %s '%s';" % (key, value)

class Python(ActionInterpreter):
    '''Execute commands in the current python session'''
    expand_env_vars = True

    def get_output(self, manager):
        os.environ.update(manager.environ)
        return manager.environ

    def setenv(self, key, value):
        settings.env_var_changed(key)

    def unsetenv(self, key):
        settings.env_var_changed(key)

    def resetenv(self, key, value, friends=None):
        settings.env_var_changed(key)

    def prependenv(self, key, value):
        settings.env_var_changed(key)
        if key == 'PYTHONPATH':
            sys.path.insert(0, value)

    def appendenv(self, key, value):
        # special case: update current python process
        settings.env_var_changed(key)
        if key == 'PYTHONPATH':
            sys.path.append(value)

    def alias(self, key, value):
        pass

    def info(self, value):
        print value

    def error(self, value):
        print>>sys.stderr, value

    def command(self, value):
        if not isinstance(value, (list, tuple)):
            import shlex
            value = shlex.split(value)
        p = subprocess.Popen(value,
                             env=self._environ)
        p.communicate()

    def comment(self, value):
        pass

    def source(self, value):
        pass

# FIMXE: this is not in working order!!! It is only here for reference
class WinShell(Shell):
    # These are variables where windows will construct the value from the value
    # from system + user + volatile environment values (in that order)
    WIN_PATH_VARS = ['PATH', 'LibPath', 'Os2LibPath']

    def __init__(self, set_global=False):
        self.set_global = set_global

    def setenv(self, key, value):
        value = value.replace('/', '\\\\')
        # Will add environment variables to user environment variables -
        # HKCU\\Environment
        # ...but not to process environment variables
#        return 'setx %s "%s"\n' % ( key, value )

        # Will TRY to add environment variables to volatile environment variables -
        # HKCU\\Volatile Environment
        # ...but other programs won't 'notice' the registry change
        # Will also add to process env. globals
#        return ('REG ADD "HKCU\\Volatile Environment" /v %s /t REG_SZ /d %s /f\n' % ( key, quotedValue )  +
#                'set "%s=%s"\n' % ( key, value ))

        # Will add to volatile environment variables -
        # HKCU\\Volatile Environment
        # ...and newly launched programs will detect this
        # Will also add to process env. globals
        if self.set_global:
            # If we have a path variable, make sure we don't include items
            # already in the user or system path, as these items will be
            # duplicated if we do something like:
            #   env.PATH += 'newPath'
            # ...and can lead to exponentially increasing the size of the
            # variable every time we do an append
            # So if an entry is already in the system or user path, since these
            # will proceed the volatile path in precedence anyway, don't add
            # it to the volatile as well
            if key in self.WIN_PATH_VARS:
                sysuser = set(self.system_env(key).split(os.pathsep))
                sysuser.update(self.user_env(key).split(os.pathsep))
                new_value = []
                for val in value.split(os.pathsep):
                    if val not in sysuser and val not in new_value:
                        new_value.append(val)
                volatile_value = os.pathsep.join(new_value)
            else:
                volatile_value = value
            # exclamation marks allow delayed expansion
            quotedValue = subprocess.list2cmdline([volatile_value])
            cmd = 'setenv -v %s %s\n' % (key, quotedValue)
        else:
            cmd = ''
        cmd += 'set %s=%s\n' % (key, value)
        return cmd

    def resetenv(self, key, value, friends=None):
        return self.setenv(key, value)

    def unsetenv(self, key):
        # env globals are not cleared until restart!
        if self.set_global:
            cmd = 'setenv -v %s -delete\n' % (key,)
        else:
            cmd = ''
        cmd += 'set %s=\n' % (key,)
        return cmd

#     def user_env(self, key):
#         return executable_output(['setenv', '-u', key])
#
#     def system_env(self, key):
#         return executable_output(['setenv', '-m', key])


shells = dict(
    bash=SH,
    sh=SH,
    tcsh=CSH,
    csh=CSH,
    python=Python)

def get_command_interpreter(shell=None):
    if shell is None:
        shell = system.shell
    if shell in shells:
        return shells[shell]
    else:
        raise ValueError("Unknown shell '%s'" % shell)

#===============================================================================
# Rex Execution Namespace
#===============================================================================

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

#-------------------------------------------------------------------------------
# Environment Classes
#-------------------------------------------------------------------------------

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
        self._environ_map.manager.getenv(self.name)

    def value(self):
        return self.get()

#     def split(self):
#         # FIXME: if value is None should we return empty list or raise an error?
#         value = self.value()
#         if value is not None:
#             return _split_env(value)
#         else:
#             return []

    def setdefault(self, value):
        '''
        set value if the variable does not yet exist
        '''
        if self:
            return self.value()
        else:
            return self.set(value)

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

    # def __add__(self, value):
    #     '''
    #     append `value` to this variable's value.

    #     returns a string
    #     '''
    #     if isinstance(value, EnvironmentVariable):
    #         value = value.value()
    #     return self.value() + value

    # def __iadd__(self, value):
    #     self.prepend(value)
    #     return self

    # def __div__(self, value):
    #     return os.path.join(self.value(), *value.split('/'))


class RexExecutor(object):
    """
    This class brings all of the components of rex together and provides the
    interface for executing rex code stored in `ResolvedPackage` instances after
    a resolve.

    The `RexExecutor` class is also responsible for providing an `ActionManager` to
    the `EnvironmentDict` and providing a variable expansion function to the
    `ActionManager`.
    """
    ALL_CAPS = re.compile('[_A-Z][_A-Z0-9]*$')

    def __init__(self, interpreter, resolve_result, globals_map=None,
                 environ=None, sys_path_append=True):
        """
        interpreter: string or `ActionInterpreter`
            the interpreter to use when executing rex actions
        globals_map : dict or None
            dictionary which comprises the main python namespace when rex code
            is executed (via the python `exec` statement). if None, defaults
            to empty dict.
        sys_path_append: bool
                whether to append OS-specific paths to PATH when creating the environment
        """
        self.globals = globals_map if globals_map is not None else {}

        self.formatter = NamespaceFormatter(self.globals)
        self.globals['format'] = self.expand
        self.sys_path_append = sys_path_append

        self.manager = ActionManager(interpreter, formatter=self.expand,
                                     parent_environ=environ)
        self.environ = EnvironmentDict(self.manager)

        self.globals['env'] = util.AttrDictWrapper(self.environ)

        for cmd, func in self.manager.get_public_methods():
            self.globals[cmd] = func

        self.resolve = resolve_result

    def expand(self, value):
        return self.formatter.format(str(value))

    def _setup_execution_namespace(self):
        # add special data objects and functions to the namespace
        self.globals['machine'] = system
        self.globals['resolve'] = Packages(self.resolve.package_resolves)
        self.globals['request'] = Packages(self.resolve.package_requests)
        self.globals['building'] = bool(os.getenv('REZ_BUILD_ENV'))
        return self

    def execute_package(self, pkg_res, commands):
        prefix = "REZ_" + pkg_res.name.upper()
        self.environ[prefix + "_VERSION"] = pkg_res.version
        self.environ[prefix + "_BASE"] = pkg_res.base
        self.environ[prefix + "_ROOT"] = pkg_res.root

        self.globals['this'] = pkg_res
        self.globals['root'] = pkg_res.root
        self.globals['base'] = pkg_res.base
        self.globals['version'] = pkg_res.version

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
        # old style:
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
        """
        metadata_commands_section: string
            name of the section in the package metdata where the commands to be
            executed should be found
        """
        # build the environment commands
        # the environment dictionary to be passed during execution of python code.
        self = self._setup_execution_namespace()

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
        self.environ["PYTHONPATH"] = os.path.join(module_root_path, 'python')
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
        """
        meta_vars: list of str
                each string is a key whos value will be saved into an
                env-var named REZ_META_<KEY> (lists are comma-separated).
        shallow_meta_vars: list of str
                same as meta-vars, but only the values from those packages directly
                requested are baked into the env var REZ_META_SHALLOW_<KEY>.
        """
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
        """
        parse a bash command and convert it to a Command action
        """
        if isinstance(cmd, list):
            cmd = cmd[0]
            pkgname = cmd[1]
        else:
            cmd = cmd
            pkgname = None

        if cmd.startswith('export '):
            var, value = cmd.split(' ', 1)[1].split('=', 1)
            # get an EnvironmentVariable instance
            var_obj = self.environ[var]
            parts = value.split(DEFAULT_ENV_SEP_MAP.get(var, os.pathsep))
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

def _test():
    print "-" * 40
    print "environ dictionary + sh self.manager"
    print "-" * 40
    d = EnvironmentDict()
    d['SIMPLESET'] = 'aaaaa'
    d['APPEND'].append('bbbbb')
    d['EXPAND'] = '$SIMPLESET/cccc'
    d['SIMPLESET'].prepend('dddd')
    d['SPECIAL'] = 'eeee'
    d['SPECIAL'].append('ffff')
    print interpret(d.manager, shell='bash',
                    env_sep_map={'SPECIAL': "';'"})

    print "-" * 40
    print "exec + routing dictionary + sh self.manager"
    print "-" * 40

    code = '''
localvar = 'AAAA'
FOO = 'bar'
SIMPLESET = 'aaaaa-{localvar}'
APPEND.append('bbbbb/{custom1}')
EXPAND = '$SIMPLESET/cccc-{custom2}'
SIMPLESET.prepend('dddd')
SPECIAL = 'eeee'
SPECIAL.append('${FOO}/ffff')
comment("testing commands:")
info("the value of localvar is {localvar}")
error("oh noes")
'''
    g = RexNamespace()
    g['custom1'] = 'one'
    g['custom2'] = 'two'
    exec code in g

    print interpret(g.manager, shell='bash',
                    env_sep_map={'SPECIAL': "';'"})

    print "-" * 40
    print "re-execute record with python self.manager"
    print "-" * 40

    import pprint
    environ = {}
    pprint.pprint(interpret(g.manager, shell='bash',
                            environ=environ))
