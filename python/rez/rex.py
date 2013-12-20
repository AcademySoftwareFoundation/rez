import os
import subprocess
import sys
import posixpath
import ntpath
import string
import re
import UserDict
import inspect
#import textwrap
import pipes
import rez.platform_ as plat


ATTR_REGEX_STR = r"([_a-z][_a-z0-9]*)([._a-z][_a-z0-9]*)*"
FUNC_REGEX_STR = r"\([a-z0-9_\-.]*\)"

DEFAULT_ENV_SEP_MAP = {'CMAKE_MODULE_PATH': ';'}

EnvExpand = string.Template

class CustomExpand(string.Template):
    pass

# Add support for {attribute.lookups}
CustomExpand.pattern = re.compile(r"""
    (?<![$])(?:                          # delimiter (anything other than $)
      (?P<escaped>a^)                |   # Escape sequence (not used)
      (?P<named>a^)                  |   # a Python identifier (not used)
      {(?P<braced>%(braced)s             # a braced identifier (with periods), AND...
        (?:%(func)s)?)}              |   # an optional simple function, OR...
      (?P<invalid>a^)                    # Other ill-formed delimiter exprs (not used)
    )
    """ % {'braced': ATTR_REGEX_STR,
           'func': FUNC_REGEX_STR}, re.IGNORECASE | re.VERBOSE)

# # Add support for !{attribute.lookups}
# CustomExpand.pattern = re.compile(r"""
#       %(delim)s(?:                     # delimiter AND...
#       (?P<escaped>%(delim)s)       |   # Escape sequence of repeated delimiter, OR...
#       (?P<named>[_a-z][_a-z0-9]*)  |   # a Python identifier, OR...
#       {(?P<braced>%(braced)s)}     |  # a braced identifier (with periods), OR...
#       (?P<invalid>)                    # Other ill-formed delimiter exprs
#     )
#     """ % {'delim': re.escape(CustomExpand.delimiter),
#            'braced': ATTR_REGEX_STR},
#     re.IGNORECASE | re.VERBOSE)

class ObjectNameDict(UserDict.UserDict):
    """
    Dictionary for doing attribute-based lookups of objects.
    """
    ATTR_REG = re.compile(ATTR_REGEX_STR + '$', re.IGNORECASE)
    FUNC_REG = re.compile("(" + FUNC_REGEX_STR + ')$', re.IGNORECASE)

    def __getitem__(self, key):
        parts = key.split('.')
        funcparts = self.FUNC_REG.split(parts[-1])
        if len(funcparts) > 1:
            parts[-1] = funcparts[0]
            funcarg = funcparts[1]
        else:
            funcarg = None
        attrs = []
        # work our way back through the hierarchy of attributes looking for an
        # object stored directly in the dict with that key.
        found = False
        while parts:
            try:
                result = self.data['.'.join(parts)]
                found = True
                break
            except KeyError:
                # pop off each failed attribute and store it for attribute lookup
                attrs.append(parts.pop())
        if not found:
            raise KeyError(key)

        attrs.reverse()
        # work our way forward through the attribute hierarchy looking up
        # attributes on the found object
        for attr in attrs:
            try:
                result = getattr(result, attr)
            except AttributeError:
                raise AttributeError("Failed to retrieve attribute '%s' of '%s' from %r" \
                                     % (attr, '.'.join(attrs), result))
        # call the result, if requested
        if funcarg:
            # strip ()
            funcarg = funcarg[1:-1]
            if not hasattr(result, '__call__'):
                raise TypeError('%r is not callable' % (result))
            if funcarg:
                result = result(funcarg)
            else:
                result = result()
        return result

    def __setitem__(self, key, value):
        if not isinstance(key, basestring):
            raise TypeError("key must be a string")
        if not self.ATTR_REG.match(key):
            raise ValueError("key must be of the format 'node.attr1.attr2': %r" % key)
        self.data[key] = value

#===============================================================================
# Commands
#===============================================================================

class BaseCommand(object):
    _registry = []

    def __init__(self, *args):
        self.args = args

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__,
                           ', '.join(repr(x) for x in self.args))

    @classmethod
    def register_command_type(cls, name, klass):
        cls._registry.append((name, klass))

    @classmethod
    def register(cls):
        cls.register_command_type(cls.name, cls)

    @classmethod
    def get_command_types(cls):
        return tuple(cls._registry)

class EnvCommand(BaseCommand):
    @property
    def key(self):
        return self.args[0]

    @property
    def value(self):
        if len(self.args) == 2:
            return self.args[1]

class Unsetenv(EnvCommand):
    name = 'unsetenv'
Unsetenv.register()

class Setenv(EnvCommand):
    name = 'setenv'

    def pre_exec(self, interpreter):
        key, value = self.args
        if isinstance(value, (list, tuple)):
            value = interpreter._env_sep(key).join(value)
            self.args = key, value

    def post_exec(self, interpreter, result):
        interpreter._set_env_vars.add(self.key)
        return result
Setenv.register()

class Prependenv(Setenv):
    name = 'prependenv'
Prependenv.register()

class Appendenv(Setenv):
    name = 'appendenv'
Appendenv.register()

class Alias(BaseCommand):
    name = 'alias'
Alias.register()

class Info(BaseCommand):
    name = 'info'
Info.register()

class Error(BaseCommand):
    name = 'error'
Error.register()

class Command(BaseCommand):
    name = 'command'
Command.register()

class Comment(BaseCommand):
    name = 'comment'
Comment.register()

class Source(BaseCommand):
    name = 'source'
Source.register()

class CommandRecorder(object):
    """
    Utility class for generating a list of `BaseCommand` instances and performing string
    variable expansion on their arguments (For local variables, not for
    environment variables)
    """
    def __init__(self, initial_commands=None):
        self.commands = [] if initial_commands is None else initial_commands
        self._expandfunc = None

    def reset_commands(self):
        self.commands = []

    def get_commands(self):
        return self.commands[:]

    def get_command_methods(self):
        """
        return a list of methods on this class for recording commands.
        methods are return as a list of (name, func) tuples
        """
        return [(name, getattr(self, name)) for name, _ in BaseCommand.get_command_types()]

    def _expand(self, value):
        if self._expandfunc:
            if isinstance(value, (list, tuple)):
                return [self._expandfunc(str(v)) for v in value]
            else:
                return self._expandfunc(str(value))
        return value

    def setenv(self, key, value):
        self.commands.append(Setenv(key, self._expand(value)))

    def unsetenv(self, key):
        self.commands.append(Unsetenv(key))

    def prependenv(self, key, value):
        self.commands.append(Prependenv(key, self._expand(value)))

    def appendenv(self, key, value):
        self.commands.append(Appendenv(key, self._expand(value)))

    def alias(self, key, value):
        self.commands.append(Alias(key, self._expand(value)))

    def info(self, value=''):
        self.commands.append(Info(self._expand(value)))

    def error(self, value):
        self.commands.append(Error(self._expand(value)))

    def command(self, value):
        self.commands.append(Command(self._expand(value)))

    def comment(self, value):
        self.commands.append(Comment(self._expand(value)))

    def source(self, value):
        self.commands.append(Source(self._expand(value)))

#===============================================================================
# Interpreters
#===============================================================================

class CommandInterpreter(object):
    """
    Abstract base class to interpret a list of commands, usually as a commands
    for a shell.

    Usually the convenience function `interpret` is used rather than accessing
    this class directly.
    """
    def __init__(self, output_style='file', env_sep_map=None, verbose=False):
        '''
        output_style : str
            the style of the output string.  currently only 'file' and 'eval' are
            supported.  'file' is intended to be more human-readable, while 'eval' is
            intended to work in a shell `eval` statement. pratically, this means the
            former is separated by newlines, while the latter is separated by
            semi-colons.
        env_sep_map : dict
            If provided, allows for custom separators for certain environment
            variables.  Should be a map of variable name to path separator.
        verbose : bool or list of str
            if True, causes commands to print additional feedback (using info()).
            can also be set to a list of strings matching command names to add
            verbosity to only those commands.
        '''
        self._output_style = output_style
        self._env_sep_map = env_sep_map if env_sep_map is not None else {}
        self._verbose = verbose
        # TODO: will probably remove these two options
        self._respect_parent_env = True
        self._set_env_vars = set([])

    def get_command_methods(self):
        """
        return a list of methods on this class for interpreting commands.
        methods are return as a list of (name, func) tuples
        """
        return [(name, getattr(self, name)) for name, _ in BaseCommand.get_command_types()]

    def _reset(self):
        self._set_env_vars = set([])

    def _is_verbose(self, command):
        if isinstance(self._verbose, (list, tuple)):
            return command in self._verbose
        else:
            return bool(self._verbose)

    def _execute(self, command_list):
        lines = []
        header = self.begin()
        if header:
            lines.append(header)

        for cmd in command_list:
            func = getattr(self, cmd.name)
            pre_func = getattr(cmd, 'pre_exec', None)
            if pre_func:
                pre_func(self)
            if self._is_verbose(cmd.name):
                self.info("running %s: %s" % (cmd.name, ' '.join(str(x) for x in cmd.args)))
            result = func(*cmd.args)
            post_func = getattr(cmd, 'post_exec', None)
            if post_func:
                result = post_func(self, result)
            if result is not None:
                lines.append(result)
        footer = self.end()
        if footer:
            lines.append(footer)
        line_sep = '\n' if self._output_style == 'file' else ';'
        script = line_sep.join(lines)
        script += line_sep
        return script

    def _env_sep(self, name):
        return self._env_sep_map.get(name, os.pathsep)

    # --- callbacks

    def begin(self):
        pass

    def end(self):
        pass

    # --- commands

    def setenv(self, key, value):
        raise NotImplementedError

    def unsetenv(self, key):
        raise NotImplementedError

    def prependenv(self, key, value):
        raise NotImplementedError

    def appendenv(self, key, value):
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

class Shell(CommandInterpreter):
    pass

class SH(Shell):
    # This caused a silent abort during rez-env. very bad.
    # def begin(self):
    #     return '# stop on error:\nset -e'

    def setenv(self, key, value):
        return 'export %s="%s"' % (key, value)

    def unsetenv(self, key):
        return "unset %s" % (key,)

    def prependenv(self, key, value):
        return 'export {key}="{value}{sep}${key}"'.format(key=key,
                                                          sep=self._env_sep(key),
                                                          value=value)

        # if key in self._set_env_vars:
        #     return 'export {key}="{value}{sep}${key}"'.format(key=key,
        #                                                       sep=self._env_sep(key),
        #                                                       value=value)
        # if not self._respect_parent_env:
        #     return self.setenv(key, value)
        # if self._output_style == 'file':
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

    def appendenv(self, key, value):
        return 'export {key}="${key}{sep}{value}"'.format(key=key,
                                                          sep=self._env_sep(key),
                                                          value=value)
        # if key in self._set_env_vars:
        #     return 'export {key}="${key}{sep}{value}"'.format(key=key,
        #                                                       sep=self._env_sep(key),
        #                                                       value=value)
        # if not self._respect_parent_env:
        #     return self.setenv(key, value)
        # if self._output_style == 'file':
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
        return "{key}() { {value}; };export -f {key};".format(key=key,
                                                              value=value)

    def info(self, value):
        # TODO: handle newlines
        return 'echo "%s"' % value

    def error(self, value):
        # TODO: handle newlines
        return 'echo "%s" 1>&2' % value

    def command(self, value):
        def quote(s):
            if '$' not in s:
                return pipes.quote(s)
            return s
        if isinstance(value, (list, tuple)):
            value = ' '.join(quote(x) for x in value)
        return str(value)

    def comment(self, value):
        # TODO: handle newlines
        return "# %s" % value

    def source(self, value):
        return 'source "%s"' % value

class CSH(SH):
    def setenv(self, key, value):
        return 'setenv %s "%s"' % (key, value)

    def unsetenv(self, key):
        return "unsetenv %s" % (key,)

    def prependenv(self, key, value):
        return 'setenv {key}="{value}{sep}${key}"'.format(key=key,
                                                          sep=self._env_sep(key),
                                                          value=value)
#         if key in self._set_env_vars:
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

    def appendenv(self, key, value):
        return 'setenv {key}="${key}{sep}{value}"'.format(key=key,
                                                          sep=self._env_sep(key),
                                                          value=value)
#         if key in self._set_env_vars:
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

class Python(CommandInterpreter):
    '''Execute commands in the current python session'''
    def __init__(self, respect_parent_env=False, environ=None):
        CommandInterpreter.__init__(self, respect_parent_env)
        self._environ = os.environ if environ is None else environ

    def _expand(self, value):
        return EnvExpand(value).safe_substitute(**self._environ)

    def _get_env_list(self, key):
        return self._environ[key].split(self._env_sep(key))

    def _set_env_list(self, key, values):
        self._environ[key] = self._env_sep(key).join(values)

    def _execute(self, command_list):
        CommandInterpreter._execute(self, command_list)
        return self._environ

    def setenv(self, key, value):
        self._environ[key] = self._expand(value)

    def unsetenv(self, key):
        self._environ.pop(key)

    def prependenv(self, key, value):
        value = self._expand(value)
        if key in self._set_env_vars or (self._respect_parent_env and key in self._environ):
            parts = self._get_env_list(key)
            parts.insert(0, value)
            self._set_env_list(key, parts)
        else:
            self._environ[key] = value
        # special case: update current python process
        if key == 'REZ_PACKAGES_PATH':
            import rez.filesys
            rez.filesys._g_syspaths.insert(0, value)
            rez.filesys._g_syspaths_nolocal.insert(0, value)
        elif key == 'PYTHONPATH':
            sys.path.insert(0, value)

    def appendenv(self, key, value):
        value = self._expand(value)
        if key in self._set_env_vars or (self._respect_parent_env and key in self._environ):
            parts = self._get_env_list(key)
            parts.append(value)
            self._set_env_list(key, parts)
        else:
            self._environ[key] = value
        # special case: update current python process
        if key == 'REZ_PACKAGES_PATH':
            import rez.filesys
            rez.filesys._g_syspaths.append(value)
            rez.filesys._g_syspaths_nolocal.append(value)
        elif key == 'PYTHONPATH':
            sys.path.append(value)

    def alias(self, key, value):
        pass

    def info(self, value):
        print str(self._expand(value))

    def error(self, value):
        print>>sys.stderr, str(self._expand(value))

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
        # Will also add to process env. vars
#        return ('REG ADD "HKCU\\Volatile Environment" /v %s /t REG_SZ /d %s /f\n' % ( key, quotedValue )  +
#                'set "%s=%s"\n' % ( key, value ))

        # Will add to volatile environment variables -
        # HKCU\\Volatile Environment
        # ...and newly launched programs will detect this
        # Will also add to process env. vars
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

    def unsetenv(self, key):
        # env vars are not cleared until restart!
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

shells = {'bash': SH,
          'sh': SH,
          'tcsh': CSH,
          'csh': CSH,
          '-csh': CSH,  # For some reason, inside of 'screen', ps -o args reports -csh...
          'python': Python,
          #          'DOS': WinShell
          }

def get_shell_name():
    proc = subprocess.Popen(['ps', '-o', 'args=', '-p', str(os.getppid())],
                            stdout=subprocess.PIPE)
    output = proc.communicate()[0]
    return output.strip().split()[0]

def get_command_interpreter(shell=None):
    if shell is None:
        shell = get_shell_name()
    return shells[os.path.basename(shell)]

def interpret(commands, shell=None, **kwargs):
    """
    Convenience function which acts as a main entry point for interpreting commands
    """
    if isinstance(commands, CommandRecorder):
        commands = commands.commands
    kwargs.setdefault('env_sep_map', DEFAULT_ENV_SEP_MAP)
    return get_command_interpreter(shell)(**kwargs)._execute(commands)

#===============================================================================
# Path Utils
#===============================================================================

if sys.version_info < (2, 7, 4):
    # TAKEN from os.posixpath in python 2.7
    # Join two paths, normalizing ang eliminating any symbolic links
    # encountered in the second path.
    def _joinrealpath(path, rest, seen):
        from os.path import isabs, sep, curdir, pardir, split, join, islink
        if isabs(rest):
            rest = rest[1:]
            path = sep

        while rest:
            name, _, rest = rest.partition(sep)
            if not name or name == curdir:
                # current dir
                continue
            if name == pardir:
                # parent dir
                if path:
                    path, name = split(path)
                    if name == pardir:
                        path = join(path, pardir, pardir)
                else:
                    path = pardir
                continue
            newpath = join(path, name)
            if not islink(newpath):
                path = newpath
                continue
            # Resolve the symbolic link
            if newpath in seen:
                # Already seen this path
                path = seen[newpath]
                if path is not None:
                    # use cached value
                    continue
                # The symlink is not resolved, so we must have a symlink loop.
                # Return already resolved part + rest of the path unchanged.
                return join(newpath, rest), False
            seen[newpath] = None  # not resolved symlink
            path, ok = _joinrealpath(path, os.readlink(newpath), seen)
            if not ok:
                return join(path, rest), False
            seen[newpath] = path  # resolved symlink

        return path, True
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
# Environment Classes
#===============================================================================

class EnvironRecorderDict(UserDict.DictMixin):
    """
    Provides a mapping interface to `EnvironmentVariable` instances,
    which provide an object-oriented interface for recording environment
    variable manipulations.

    `__getitem__` is always guaranteed to return an `EnvironmentVariable`
    instance: it will not raise a KeyError.
    """
    def __init__(self, command_recorder=None, environ=None, override_existing_lists=False):
        """
        override_existing_lists : bool
            If True, the first call to append or prepend will override the
            value in `environ` and effectively act as a setenv operation.
            If False, pre-existing values will be appended/prepended to as usual.
        """
        self.command_recorder = command_recorder if command_recorder is not None else CommandRecorder()
        # make a copy of os.environ so we don't change the current environment.
        # if that is desired the changes can be played back with the Python CommandInterpreter
        self.environ = environ if environ is not None else dict(os.environ)
        # use a python command interpreter to track updates to self.environ
        self.python_interpreter = Python(environ=self.environ)
        self._override_existing_lists = override_existing_lists
        self._var_cache = {}

    def set_command_recorder(self, recorder):
        self.command_recorder = recorder

    def get_command_recorder(self):
        return self.command_recorder

    def do_list_override(self, key):
        if key not in self.environ:
            return True
        if self._override_existing_lists and key not in self._var_cache:
            return True
        return False

    def __getitem__(self, key):
        if key not in self._var_cache:
            self._var_cache[key] = EnvironmentVariable(key, self)
        return self._var_cache[key]

    def __setitem__(self, key, value):
        self[key].set(value)

class EnvironmentVariable(object):
    '''
    class representing an environment variable

    combined with EnvironRecorderDict class, records changes to the environment
    '''

    def __init__(self, name, environ_map):
        self._name = name
        self._environ_map = environ_map

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._name)

    @property
    def name(self):
        return self._name

    @property
    def environ(self):
        return self._environ_map.environ

    def prepend(self, value):
        if self. _environ_map.do_list_override(self.name):
            self._environ_map.python_interpreter.setenv(self.name, value)
            self._environ_map.command_recorder.setenv(self.name, value)
        else:
            self._environ_map.python_interpreter.prependenv(self.name, value)
            self._environ_map.command_recorder.prependenv(self.name, value)

    def append(self, value):
        if self. _environ_map.do_list_override(self.name):
            self._environ_map.python_interpreter.setenv(self.name, value)
            self._environ_map.command_recorder.setenv(self.name, value)
        else:
            self._environ_map.python_interpreter.appendenv(self.name, value)
            self._environ_map.command_recorder.appendenv(self.name, value)

    def set(self, value):
        self._environ_map.command_recorder.setenv(self.name, value)

    def unset(self):
        self._environ_map.command_recorder.unsetenv(self.name)

    # --- the following methods all require knowledge of the current environment

    def value(self):
        return self.environ.get(self._name, '')

    def split(self):
        # FIXME: if value is None should we return empty list or raise an error?
        value = self.value()
        if value is not None:
            return _split_env(value)
        else:
            return []

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

class RexNamespace(dict):
    """
    The RexNamespace is a custom dictionary that brings all of the components of
    rex together into a single dictionary interface, which can act as a namespace
    dictionary for use with the python `exec` statement.

    The class routes key lookups between an `EnvironRecorderDict` and a dictionary of
    local variables passed in via `vars`. Keys which are ALL_CAPS will be looked
    up in the `EnvironRecorderDict`, and the remainder will be looked up in the `vars` dict.

    The `RexNamespace` is also responsible for providing a `CommandRecorder` to
    the `EnvironRecorderDict` and providing a variable expansion function to the
    `CommandRecorder`.  It is also responsible for expanding variables which
    are set directly via `__setitem__`.
    """
    ALL_CAPS = re.compile('[_A-Z][_A-Z0-9]*$')

    def __init__(self, vars=None, environ=None, env_overrides_existing_lists=False):
        """
        vars : dict or None
            dictionary which comprises the primary data of the `RexNamespace`
            and will form the main namespace when it is used with `exec`.
            if None, defaults to empty dict.
        environ : dict or None
            dictionary of environment variables, used as reference by `EnvironRecorderDict`
            if None, defaults to `os.environ`.
        env_overrides_existing_lists: bool
            If True, the first call to append or prepend will override the
            value in `environ` and effectively act as a setenv operation.
            If False, pre-existing values will be appended/prepended to as usual.
        """
        self.command_recorder = CommandRecorder()
        self.command_recorder._expandfunc = self.expand
        self.environ = EnvironRecorderDict(self.command_recorder,
                                           environ,
                                           override_existing_lists=env_overrides_existing_lists)
        self.vars = vars if vars is not None else {}
        self.custom = ObjectNameDict()
        self.custom.data = self.vars  # assigning to data directly keeps a live link

        # load commands into environment
        for cmd, func in self.command_recorder.get_command_methods():
            self.vars[cmd] = func

    def expand(self, value):
        value = CustomExpand(value).substitute(self.custom)
        return value

    def set_command_recorder(self, recorder):
        self.command_recorder = recorder
        self.command_recorder._expandfunc = self.expand
        self.environ.set_command_recorder(recorder)

    def get_command_recorder(self):
        return self.command_recorder

    def set(self, key, value, expand=True):
        if self.ALL_CAPS.match(key):
            self.environ[key] = value
        else:
            if expand and isinstance(value, basestring):
                value = self.expand(value)
            self.vars[key] = value

    def __getitem__(self, key):
        if self.ALL_CAPS.match(key):
            return self.environ[key]
        else:
            return self.vars[key]

    def __setitem__(self, key, value):
        self.set(key, value)


def _test_string_template():
    print CustomExpand.pattern.search('foo {this.that}').group('braced')
    # fail
    print CustomExpand.pattern.search('foo ${this.that}')
    print CustomExpand.pattern.search('{this.that}').group('braced')
    print CustomExpand.pattern.search('{this.that(12)}').group('braced')
    print CustomExpand.pattern.search('{this.that(x.x.x)}').group('braced')

def _test_attr_dict():

    class Foo(str):
        bar = 'value'

        def myfunc(self, arg):
            return arg * 10

    f = Foo('this is the string')
    custom = ObjectNameDict({'thing.name': 'name',
                             'thing': f})
    print custom['thing']
    print custom['thing.bar']
    print custom['thing.myfunc(1)']

def _test():
    print "-" * 40
    print "environ dictionary + sh executor"
    print "-" * 40
    d = EnvironRecorderDict()
    d['SIMPLESET'] = 'aaaaa'
    d['APPEND'].append('bbbbb')
    d['EXPAND'] = '$SIMPLESET/cccc'
    d['SIMPLESET'].prepend('dddd')
    d['SPECIAL'] = 'eeee'
    d['SPECIAL'].append('ffff')
    print interpret(d.command_recorder, shell='bash',
                    env_sep_map={'SPECIAL': "';'"})

    print "-" * 40
    print "exec + routing dictionary + sh executor"
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

    print interpret(g.command_recorder, shell='bash',
                    env_sep_map={'SPECIAL': "';'"})

    print "-" * 40
    print "re-execute record with python executor"
    print "-" * 40

    import pprint
    environ = {}
    pprint.pprint(interpret(g.command_recorder, shell='bash',
                            environ=environ))
