from __future__ import print_function

import os
import sys
import re
import traceback
from contextlib import contextmanager
from string import Formatter

from rez.system import system
from rez.config import config
from rez.exceptions import RexError, RexUndefinedVariableError, \
    RezSystemError, _NeverError
from rez.util import shlex_join, is_non_string_iterable
from rez.utils import reraise
from rez.utils.execution import Popen
from rez.utils.sourcecode import SourceCode, SourceCodeError
from rez.utils.data_utils import AttrDictWrapper
from rez.utils.formatting import expandvars
from rez.utils.platform_ import platform_
from rez.vendor.enum import Enum
from rez.vendor.six import six


basestring = six.string_types[0]

# http://python3porting.com/problems.html#replacing-userdict
if six.PY2:
    from UserDict import DictMixin
else:
    from collections.abc import MutableMapping as DictMixin


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


class Prependenv(Setenv):
    name = 'prependenv'


class Appendenv(Setenv):
    name = 'appendenv'


class Alias(Action):
    name = 'alias'


class Info(Action):
    name = 'info'


class Error(Action):
    name = 'error'


class Stop(Action):
    name = 'stop'


class Command(Action):
    name = 'command'


class Comment(Action):
    name = 'comment'


class Source(Action):
    name = 'source'


class Shebang(Action):
    name = 'shebang'


Unsetenv.register()
Setenv.register()
Resetenv.register()
Prependenv.register()
Appendenv.register()
Alias.register()
Info.register()
Error.register()
Stop.register()
Command.register()
Comment.register()
Source.register()
Shebang.register()


#===============================================================================
# Action Manager
#===============================================================================

class OutputStyle(Enum):
    """ Enum to represent the style of code output when using Rex.
    """
    file = ("Code as it would appear in a script file.", )
    eval = ("Code in a form that can be evaluated.", )


class ActionManager(object):
    """Handles the execution book-keeping.  Tracks env variable values, and
    triggers the callbacks of the `ActionInterpreter`.
    """
    def __init__(self, interpreter, parent_environ=None, parent_variables=None,
                 formatter=None, verbose=False, env_sep_map=None):
        '''
        interpreter: string or `ActionInterpreter`
            the interpreter to use when executing rex actions
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
        self.verbose = verbose
        self.parent_environ = os.environ if parent_environ is None else parent_environ
        self.parent_variables = True if parent_variables is True \
            else set(parent_variables or [])
        self.environ = {}
        self.formatter = formatter or str
        self.actions = []

        self._env_sep_map = env_sep_map if env_sep_map is not None \
            else config.env_var_separators

    def get_action_methods(self):
        """
        return a list of methods on this class for executing actions.
        methods are return as a list of (name, func) tuples
        """
        return [(name, getattr(self, name))
                for name, _ in Action.get_command_types()]

    def get_public_methods(self):
        """
        return a list of methods on this class which should be exposed in the rex
        API.
        """
        return self.get_action_methods() + [
            ('getenv', self.getenv),
            ('expandvars', self.expandvars),
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
        # It would be unexpected to get var expansion on the str repr of an
        # object, so don't do that.
        #
        if not isinstance(value, (basestring, EscapedString)):
            return str(value)

        # Perform expansion on non-literal parts of the string. If any
        # expansion fails, just return unformatted string.
        #
        try:
            return EscapedString.promote(value).formatted(self.formatter)
        except (KeyError, ValueError):
            return value

    def _expand(self, value):
        def _fn(str_):
            str_ = expandvars(str_, self.environ)
            str_ = expandvars(str_, self.parent_environ)
            return os.path.expanduser(str_)

        return EscapedString.promote(value).formatted(_fn)

    def _key(self, key):
        # returns (unexpanded, expanded) forms of key
        unexpanded_key = str(self._format(key))
        expanded_key = str(self._expand(unexpanded_key))
        return unexpanded_key, expanded_key

    def _value(self, value):
        # returns (unexpanded, expanded) forms of value
        unexpanded_value = self._format(value)
        expanded_value = self._expand(unexpanded_value)
        return unexpanded_value, expanded_value

    def get_output(self, style=OutputStyle.file):
        return self.interpreter.get_output(style=style)

    # -- Commands

    def undefined(self, key):
        _, expanded_key = self._key(key)
        return (
            expanded_key not in self.environ
            and expanded_key not in self.parent_environ
        )

    def defined(self, key):
        return not self.undefined(key)

    def expandvars(self, value, format=True):
        if format:
            value = str(self._format(value))
        return str(self._expand(value))

    def getenv(self, key):
        _, expanded_key = self._key(key)
        try:
            return self.environ[expanded_key] if expanded_key in self.environ \
                else self.parent_environ[expanded_key]
        except KeyError:
            raise RexUndefinedVariableError(
                "Referenced undefined environment variable: %s" % expanded_key)

    def setenv(self, key, value):
        unexpanded_key, expanded_key = self._key(key)
        unexpanded_value, expanded_value = self._value(value)

        # TODO: check if value has already been set by another package
        self.actions.append(Setenv(unexpanded_key, unexpanded_value))
        self.environ[expanded_key] = str(expanded_value)

        if self.interpreter.expand_env_vars:
            key, value = expanded_key, expanded_value
        else:
            key, value = unexpanded_key, unexpanded_value
        self.interpreter.setenv(key, value)

    def unsetenv(self, key):
        unexpanded_key, expanded_key = self._key(key)
        self.actions.append(Unsetenv(unexpanded_key))

        if expanded_key in self.environ:
            del self.environ[expanded_key]
        if self.interpreter.expand_env_vars:
            key = expanded_key
        else:
            key = unexpanded_key
        self.interpreter.unsetenv(key)

    def resetenv(self, key, value, friends=None):
        unexpanded_key, expanded_key = self._key(key)
        unexpanded_value, expanded_value = self._value(value)

        action = Resetenv(unexpanded_key, unexpanded_value, friends)
        self.actions.append(action)
        self.environ[expanded_key] = str(expanded_value)

        if self.interpreter.expand_env_vars:
            key, value = expanded_key, expanded_value
        else:
            key, value = unexpanded_key, unexpanded_value
        self.interpreter.resetenv(key, value)

    def _pendenv(self, key, value, action, interpfunc, addfunc):
        unexpanded_key, expanded_key = self._key(key)
        unexpanded_value, expanded_value = self._value(value)

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
            env_sep = self._env_sep(expanded_key)
            self.actions.append(action(unexpanded_key, unexpanded_value))

            values = addfunc(unexpanded_value, [self._keytoken(expanded_key)])
            unexpanded_values = EscapedString.join(env_sep, values)

            parts = self.environ[expanded_key].split(env_sep)
            values = addfunc(expanded_value, parts)
            expanded_values = EscapedString.join(env_sep, values)

            self.environ[expanded_key] = \
                env_sep.join(addfunc(str(expanded_value), parts))
        else:
            self.actions.append(Setenv(unexpanded_key, unexpanded_value))
            self.environ[expanded_key] = str(expanded_value)
            unexpanded_values = unexpanded_value
            expanded_values = expanded_value
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
        key = str(self._format(key))
        value = str(self._format(value))
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

    def stop(self, msg, *nargs):
        from rez.exceptions import RexStopError
        raise RexStopError(msg % nargs)

    def command(self, value):
        # Note: Value is deliberately not formatted in commands
        self.actions.append(Command(value))
        self.interpreter.command(value)

    def comment(self, value):
        value = str(self._format(value))
        self.actions.append(Comment(value))
        self.interpreter.comment(value)

    def source(self, value):
        value = str(self._format(value))
        self.actions.append(Source(value))
        self.interpreter.source(value)

    def shebang(self):
        self.actions.append(Shebang())
        self.interpreter.shebang()

    def _keytoken(self, key):
        return self.interpreter.get_key_token(key)


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

    # RegEx that captures environment variables (generic form).
    # Extend/override to regex formats that can capture environment formats
    # in other interpreters like shells if needed
    ENV_VAR_REGEX = re.compile(
        "|".join([
            "\\${([^\\{\\}]+?)}",               # ${ENVVAR}
            "\\$([a-zA-Z_]+[a-zA-Z0-9_]*?)",    # $ENVVAR
        ])
    )

    def get_output(self, style=OutputStyle.file):
        """Returns any implementation specific data.

        Args:
            style (`OutputStyle`): Style affecting output format.

        Returns:
            Depends on implementation, but usually a code string.
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

    # --- other

    def escape_string(self, value):
        """Escape a string.

        Escape the given string so that special characters (such as quotes and
        whitespace) are treated properly. If `value` is a string, assume that
        this is an expandable string in this interpreter.

        Note:
            This default implementation returns the string with no escaping
            applied.

        Args:
            value (str or `EscapedString`): String to escape.
        """
        return str(value)

    # --- internal commands, not exposed to public rex API

    def _saferefenv(self, key):
        '''
        make the var safe to reference, even if it does not yet exist. This is
        needed because of different behaviours in shells - eg, tcsh will fail
        on ref to undefined var, but sh will expand to the empty string.
        '''
        raise NotImplementedError

    # --- internal functions

    def _bind_interactive_rez(self):
        '''
        apply changes to the env needed to expose rez in an interactive shell,
        for eg prompt change, sourcing completion scripts etc. Do NOT add rez
        to PATH, this is done elsewhere.
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
            only applied to target_environ. In either case you must call
            `apply_environ` to flush all changes to the target environ dict.

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

    def apply_environ(self):
        """Apply changes to target environ.
        """
        if self.manager is None:
            raise RezSystemError("You must call 'set_manager' on a Python rex "
                                 "interpreter before using it.")

        self.target_environ.update(self.manager.environ)
        self.adjust_env_for_platform(self.target_environ)

    def get_output(self, style=OutputStyle.file):
        self.apply_environ()
        return self.manager.environ

    def setenv(self, key, value):
        if self.update_session:
            if key == 'PYTHONPATH':
                value = self.escape_string(value)
                sys.path = value.split(os.pathsep)

    def unsetenv(self, key):
        pass

    def resetenv(self, key, value, friends=None):
        pass

    def prependenv(self, key, value):
        if self.update_session:
            if key == 'PYTHONPATH':
                value = self.escape_string(value)
                sys.path.insert(0, value)

    def appendenv(self, key, value):
        if self.update_session:
            if key == 'PYTHONPATH':
                value = self.escape_string(value)
                sys.path.append(value)

    def info(self, value):
        if not self.passive:
            value = self.escape_string(value)
            print(value)

    def error(self, value):
        if not self.passive:
            value = self.escape_string(value)
            print(value, file=sys.stderr)

    def subprocess(self, args, **subproc_kwargs):
        if self.manager:
            self.target_environ.update(self.manager.environ)
        self.adjust_env_for_platform(self.target_environ)

        shell_mode = isinstance(args, basestring)
        return Popen(args,
                     shell=shell_mode,
                     env=self.target_environ,
                     **subproc_kwargs)

    def command(self, value):
        if self.passive:
            return

        if is_non_string_iterable(value):
            it = iter(value)
            cmd = EscapedString.disallow(next(it))
            value = [cmd] + [self.escape_string(x) for x in it]
        else:
            value = EscapedString.disallow(value)
            value = self.escape_string(value)

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

    def get_key_token(self, key):
        # Not sure if this actually needs to be returned here.  Prior to the
        # Windows refactor this is the value this interpretter was receiving,
        # but the concept doesn't really feel applicable to Python.  It's just
        # here because the API requires it.
        return "${%s}" % key

    def adjust_env_for_platform(self, env):
        """ Make required platform-specific adjustments to env.
        """
        if platform_.name == "windows":
            self._add_systemroot_to_env_win32(env)

    def _add_systemroot_to_env_win32(self, env):
        r""" Sets ``%SYSTEMROOT%`` environment variable, if not present
        in :py:attr:`target_environ` .

        Args:
            env (dict): desired environment variables

        Notes:
            on windows, python-3.6 startup fails within an environment
            where it ``%PATH%`` includes python3, but ``%SYSTEMROOT%`` is not
            present.

            for example.

            .. code-block:: python

                from subprocess import Popen
                cmds = ['python', '--version']

                # successful
                Popen(cmds)
                Popen(cmds, env={'PATH': 'C:\\Python-3.6.5',
                                 'SYSTEMROOT': 'C:\Windows'})

                # failure
                Popen(cmds, env={'PATH': 'C:\\Python-3.6.5'})

                #> Fatal Python Error: failed to get random numbers to initialize Python

        """
        # 'SYSTEMROOT' unecessary unless 'PATH' is set.
        if env is None:
            return
        # leave SYSTEMROOT alone if set by user
        if 'SYSTEMROOT' in env:
            return
        # not enough info to set SYSTEMROOT
        if 'SYSTEMROOT' not in os.environ:
            return

        env['SYSTEMROOT'] = os.environ['SYSTEMROOT']


#===============================================================================
# String manipulation
#===============================================================================

class EscapedString(object):
    """Class for constructing literal or expandable strings, or a combination
    of both.

    This determines how a string is escaped in an interpreter. For example,
    the following rex commands may result in the bash code shown:

        >>> env.FOO = literal('oh "noes"')
        >>> env.BAH = expandable('oh "noes"')
        export FOO='oh "noes"'
        export BAH="oh \"noes\""

    You do not need to use `expandable` - a string by default is interpreted as
    expandable. However you can mix literals and expandables together, like so:

        >>> env.FOO = literal("hello").expandable(" ${DUDE}")
        export FOO='hello'" ${DUDE}"

    Shorthand methods `e` and `l` are also supplied, for better readability:

        >>> env.FOO = literal("hello").e(" ${DUDE}").l(", and welcome!")
        export FOO='hello'" ${DUDE}"', and welcome!'

    Note:
        you can use the `literal` and `expandable` free functions, rather than
        constructing a class instance directly.
    """
    def __init__(self, value, is_literal=False):
        self.strings = [(is_literal, value)]

    def copy(self):
        other = EscapedString.__new__(EscapedString)
        other.strings = self.strings[:]
        return other

    def literal(self, value):
        self._add(value, True)
        return self

    def expandable(self, value):
        self._add(value, False)
        return self

    def l(self, value):  # noqa
        return self.literal(value)

    def e(self, value):
        return self.expandable(value)

    def _add(self, value, is_literal):
        last = self.strings[-1]
        if last[0] == is_literal:
            self.strings[-1] = (last[0], last[1] + value)
        else:
            self.strings.append((is_literal, value))

    def __str__(self):
        """Return the string unescaped."""
        return ''.join(x[1] for x in self.strings)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.strings)

    def __eq__(self, other):
        if isinstance(other, basestring):
            return (str(self) == str(other))
        else:
            return (
                isinstance(other, EscapedString)
                and other.strings == self.strings
            )

    def __ne__(self, other):
        return not (self == other)

    def __add__(self, other):
        """Join two escaped strings together.

        Returns:
            `EscapedString` object.
        """
        result = self.copy()
        other = EscapedString.promote(other)

        for is_literal, value in other.strings:
            result._add(value, is_literal)
        return result

    def expanduser(self):
        """Analogous to os.path.expanduser.

        Returns:
            `EscapedString` object with expanded '~' references.
        """
        return self.formatted(os.path.expanduser)

    def formatted(self, func):
        """Return the string with non-literal parts formatted.

        Args:
            func (callable): Callable that translates a string into a
                formatted string.

        Returns:
            `EscapedString` object.
        """
        other = EscapedString.__new__(EscapedString)
        other.strings = []

        for is_literal, value in self.strings:
            if not is_literal:
                value = func(value)
            other.strings.append((is_literal, value))
        return other

    def split(self, delimiter=None):
        """Same as string.split(), but retains literal/expandable structure.

        Returns:
            List of `EscapedString`.
        """
        result = []
        strings = self.strings[:]
        current = None

        while strings:
            is_literal, value = strings[0]
            parts = value.split(delimiter, 1)
            if len(parts) > 1:
                value1, value2 = parts
                strings[0] = (is_literal, value2)
                out = EscapedString(value1, is_literal)
                push = True
            else:
                strings = strings[1:]
                out = EscapedString(value, is_literal)
                push = False

            if current is None:
                current = out
            else:
                current = current + out
            if push:
                result.append(current)
                current = None

        if current:
            result.append(current)
        return result

    @classmethod
    def join(cls, sep, values):
        if not values:
            return EscapedString('')

        it = iter(values)
        result = EscapedString.promote(next(it))

        for value in it:
            result = result + sep
            result = result + value

        return result

    @classmethod
    def promote(cls, value):
        if isinstance(value, cls):
            return value
        else:
            return cls(value)

    @classmethod
    def demote(cls, value):
        if isinstance(value, cls):
            return str(value)
        else:
            return value

    @classmethod
    def disallow(cls, value):
        if isinstance(value, cls):
            raise RexError("The command does not accept use of 'literal' or 'expandable'")
        return value


def literal(value):
    """Creates a literal string."""
    return EscapedString(value, True)


def expandable(value):
    """Creates an expandable string."""
    return EscapedString(value, False)


def optionvars(name, default=None):
    """Access arbitrary data from rez config setting 'optionvars'.

    Args:
        name (str): Name of the optionvar. Use dot notation for values in
            nested dicts.
        default (object): Default value if setting is missing.
    """
    value = config.optionvars or {}
    parts = name.split('.')

    for i, key in enumerate(parts):
        if not isinstance(value, dict):
            raise RexError(
                "Optionvar %r is invalid because %r is not a dict"
                % (name, '.'.join(parts[:i]))
            )

        value = value.get(key, KeyError)
        if value is KeyError:
            return default

    return value


#===============================================================================
# Rex Execution Namespace
#===============================================================================

class NamespaceFormatter(Formatter):
    """String formatter that, as well as expanding '{variable}' strings, also
    protects environment variable references such as ${THIS} so they do not get
    expanded as though {THIS} is a formatting target. Also, environment variable
    references such as $THIS are converted to ${THIS}, which gives consistency
    across shells, and avoids some problems with non-curly-braced variables in
    some situations.
    """

    def __init__(self, namespace):
        Formatter.__init__(self)
        self.initial_namespace = namespace
        self.namespace = self.initial_namespace

    def format(self, format_string, *args, **kwargs):
        def escape_envvar(matchobj):
            value = next((x for x in matchobj.groups() if x is not None))
            return "${{%s}}" % value

        regex = kwargs.get("regex") or ActionInterpreter.ENV_VAR_REGEX

        format_string_ = re.sub(regex, escape_envvar, format_string)

        # for recursive formatting, where a field has a value we want to expand,
        # add kwargs to namespace, so format_field can use them...
        if kwargs:
            prev_namespace = self.namespace
            self.namespace = dict(prev_namespace)
            self.namespace.update(kwargs)
        else:
            prev_namespace = None
        try:
            return Formatter.format(self, format_string_, *args, **kwargs)
        finally:
            if prev_namespace is not None:
                self.namespace = prev_namespace

    def format_field(self, value, format_spec):
        if isinstance(value, EscapedString):
            value = str(value.formatted(str))
        if isinstance(value, str):
            value = self.format(value)
        return format(value, format_spec)

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

class EnvironmentDict(DictMixin):
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
                               for k in manager.parent_environ.keys())

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

    def __delitem__(self, key):
        del self._var_cache[key]

    def __iter__(self):
        for key in self._var_cache.keys():
            yield key

    def __len__(self):
        return len(self._var_cache)


class EnvironmentVariable(object):
    '''
    class representing an environment variable

    combined with EnvironmentDict class, records changes to the environment
    '''
    def __init__(self, name, environ_map):
        self._name = name
        self._environ_map = environ_map

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

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self._name,
                               self.value())

    def __nonzero__(self):
        return bool(self.value())

    __bool__ = __nonzero__  # py3 compat

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
                 parent_variables=None, shebang=True, add_default_namespaces=True):
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
        shebang: bool
            if True, apply a shebang to the result.
        add_default_namespaces: bool
            whether to add default namespaces such as 'system'.
        """
        self.globals = globals_map or {}
        self.formatter = NamespaceFormatter(self.globals)

        self.bind('format', self.expand)
        self.bind('literal', literal)
        self.bind('expandable', expandable)
        self.bind('optionvars', optionvars)

        if interpreter is None:
            interpreter = Python(target_environ={})

        self.manager = ActionManager(interpreter,
                                     formatter=self.expand,
                                     parent_environ=parent_environ,
                                     parent_variables=parent_variables)

        if isinstance(interpreter, Python):
            interpreter.set_manager(self.manager)

        if shebang:
            self.manager.shebang()

        self.environ = EnvironmentDict(self.manager)
        self.bind('env', AttrDictWrapper(self.environ))

        for cmd, func in self.manager.get_public_methods():
            self.bind(cmd, func)

        if add_default_namespaces:
            self.bind('system', system)

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
        """Binds an object to the execution context.

        Args:
            name (str) Variable name to bind to.
            obj (object): Object to bind.
        """
        self.globals[name] = obj

    def unbind(self, name):
        """Unbind an object from the execution context.

        Has no effect if the binding does not exist.

        Args:
            name (str) Variable name to bind to.
        """
        self.globals.pop(name, None)

    @contextmanager
    def reset_globals(self):
        """Remove changes to globals dict post-context.

        Any bindings (self.bind) will only be visible during this context.
        """

        # we want to execute the code using self.globals - if for no other
        # reason that self.formatter is pointing at self.globals, so if we
        # passed in a copy, we would also need to make self.formatter "look" at
        # the same copy - but we don't want to "pollute" our namespace, because
        # the same executor may be used to run multiple packages. Therefore,
        # we save a copy of self.globals before execution, and restore it after
        #
        saved_globals = dict(self.globals)

        try:
            yield

        finally:
            self.globals.clear()
            self.globals.update(saved_globals)

    def append_system_paths(self):
        """Append system paths to $PATH."""
        from rez.shells import Shell, create_shell
        sh = self.interpreter if isinstance(self.interpreter, Shell) \
            else create_shell()

        paths = sh.get_syspaths()
        paths_str = os.pathsep.join(paths)
        self.env.PATH.append(paths_str)

    def prepend_rez_path(self):
        """Prepend rez path to $PATH."""
        if system.rez_bin_path:
            self.env.PATH.prepend(system.rez_bin_path)

    def append_rez_path(self):
        """Append rez path to $PATH."""
        if system.rez_bin_path:
            self.env.PATH.append(system.rez_bin_path)

    @classmethod
    def compile_code(cls, code, filename=None, exec_namespace=None):
        """Compile and possibly execute rex code.

        Args:
            code (str or SourceCode): The python code to compile.
            filename (str): File to associate with the code, will default to
                '<string>'.
            exec_namespace (dict): Namespace to execute the code in. If None,
                the code is not executed.

        Returns:
            Compiled code object.
        """
        if filename is None:
            if isinstance(code, SourceCode):
                filename = code.sourcename
            else:
                filename = "<string>"

        # compile
        try:
            if isinstance(code, SourceCode):
                pyc = code.compiled
            else:
                pyc = compile(code, filename, 'exec')
        except SourceCodeError as e:
            reraise(e, RexError)
        except:
            stack = traceback.format_exc()
            raise RexError("Failed to compile %s:\n\n%s" % (filename, stack))

        exc_type = Exception if config.catch_rex_errors else _NeverError

        # execute
        if exec_namespace is not None:
            try:
                if isinstance(code, SourceCode):
                    code.exec_(globals_=exec_namespace)
                else:
                    exec(pyc, exec_namespace)
            except RexError:
                raise
            except SourceCodeError as e:
                reraise(e, RexError)
            except exc_type:
                stack = traceback.format_exc()
                raise RexError("Failed to exec %s:\n\n%s" % (filename, stack))

        return pyc

    def execute_code(self, code, filename=None, isolate=False):
        """Execute code within the execution context.

        Args:
            code (str or SourceCode): Rex code to execute.
            filename (str): Filename to report if there are syntax errors.
            isolate (bool): If True, do not affect `self.globals` by executing
                this code. DEPRECATED - use `self.reset_globals` instead.
        """
        def _apply():
            self.compile_code(code=code,
                              filename=filename,
                              exec_namespace=self.globals)

        if isolate:
            with self.reset_globals():
                _apply()
        else:
            _apply()

    def execute_function(self, func, *nargs, **kwargs):
        """
        Execute a function object within the execution context.
        @returns The result of the function call.
        """
        # makes a copy of the func
        import types
        fn = types.FunctionType(func.__code__,
                                func.__globals__.copy(),
                                name=func.__name__,
                                argdefs=func.__defaults__,
                                closure=func.__closure__)
        fn.__globals__.update(self.globals)

        exc_type = Exception if config.catch_rex_errors else _NeverError

        try:
            return fn(*nargs, **kwargs)
        except RexError:
            raise
        except exc_type:
            from inspect import getfile

            stack = traceback.format_exc()
            filename = getfile(func)

            raise RexError("Failed to exec %s:\n\n%s" % (filename, stack))

    def get_output(self, style=OutputStyle.file):
        """Returns the result of all previous calls to execute_code."""
        return self.manager.get_output(style=style)

    def expand(self, value):
        return self.formatter.format(str(value), regex=self.interpreter.ENV_VAR_REGEX)


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
