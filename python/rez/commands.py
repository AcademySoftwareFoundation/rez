import subprocess
import os
import os.path
import sys

ALL_CAPS = re.compile('[A-Z][A-Z0-9]*')

#------------------------------------------------
# Shell Classes
#------------------------------------------------

class Shell(object):
    def __init__(self, **kwargs):
        pass

    def prefix(self):
        '''
        Abstract base class representing a system shell.
        '''
        return ''
    def setenv(self, key, value):
        raise NotImplementedError
    def unsetenv(self, key):
        raise NotImplementedError
    def alias(self, key, value):
        raise NotImplementedError

class Bash(Shell):
    def setenv(self, key, value):
        return "export %s=%s;" % ( key, value )
    def unsetenv(self, key):
        return "unset %s;" % ( key, )
    def alias(self, key, value):
        return "alias %s='%s';" % ( key, value)

class Tcsh(Shell):
    def setenv(self, key, value):
        return "setenv %s %s;" % ( key, value )
    def unsetenv(self, key):
        return "unsetenv %s;" % ( key, )
    def alias(self, key, value):
        return "alias %s '%s';" % ( key, value)

class WinShell(Shell):
    def __init__(self, set_global=False):
        self.set_global = set_global
    def setenv(self, key, value):
        value = value.replace('/', '\\\\')
        # exclamation marks allow delayed expansion
        quoted_value = subprocess.list2cmdline([value])
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
            cmd = 'setenv -v %s %s\n' % (key, quoted_value)
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

shells = { 'bash' : Bash,
           'sh'   : Bash,
           'tcsh' : Tcsh,
           'csh'  : Tcsh,
           '-csh' : Tcsh, # For some reason, inside of 'screen', ps -o args reports -csh...
           'DOS' : WinShell}

def get_shell_name():
    command = executableOutput(['ps', '-o', 'args=', '-p', str(os.getppid())]).strip()
    return command.split()[0]

def get_shell_class(shell_name):
    if shell_name is None:
        shell_name = get_shell_name()
    return shells[os.path.basename(shell_name)]

#------------------------------------------------
# Environment Classes
#------------------------------------------------


def _expand(value, strip_quotes=False):
    # use posixpath because setpkg expects posix-style paths and variable expansion
    # (on windows: os.path.expandvars will not expand $FOO-x64)
    expanded = os.path.normpath(os.path.expanduser(posixpath.expandvars(value)))
    if strip_quotes:
        expanded = expanded.strip('"')
    return expanded

def _split(value):
    return value.split(os.pathsep)

def _join(values):
    return os.pathsep.join(values)

def _nativepath(path):
    return os.path.join(path.split('/'))

def prependenv(name, value, expand=True, no_dupes=False):
    if expand:
        value = _expand(value, strip_quotes=True)

    if name not in os.environ:
        os.environ[name] = value
    else:
        current_value = os.environ[name]
        parts = _split(current_value)
        if no_dupes:
            if expand:
                expanded_parts = [_expand(x) for x in parts]
            else:
                expanded_parts = parts
            if value not in expanded_parts:
                parts.insert(0, value)
                new_value = _join(parts)
                os.environ[name] = new_value
        else:
            parts.insert(0, value)
            new_value = _join(parts)
            os.environ[name] = new_value
    #print "prepend", name, value
    return value

def appendenv(name, value, expand=True, no_dupes=False):
    if expand:
        value = _expand(value, strip_quotes=True)

    if name not in os.environ:
        os.environ[name] = value
    else:
        current_value = os.environ[name]
        parts = _split(current_value)
        if no_dupes:
            if expand:
                expanded_parts = [_expand(x) for x in parts]
            else:
                expanded_parts = parts
            if value not in expanded_parts:
                parts.append(value)
                new_value = _join(parts)
                os.environ[name] = new_value
        else:
            parts.append(value)
            new_value = _join(parts)
            os.environ[name] = new_value
    #print "prepend", name, value
    return value

def prependenvs(name, value):
    '''
    like prependenv, but in addition to setting single values, it also allows
    value to be a separated list of values (foo:bar) or a python list
    '''
    if isinstance(value, (list, tuple)):
        parts = value
    else:
        parts = _split(value)
    # traverse in reverse order, so precedence given is maintained
    for part in reversed(parts):
        prependenv(name, part)
    return value

def setenv(name, value, expand=True):
    if expand:
        value = _expand(value, strip_quotes=True)
    os.environ[name] = value
    #print "set", name, value
    return value

def popenv(name, value, expand=True):
    if expand:
        value = _expand(value, strip_quotes=True)

    try:
        current_value = os.environ[name]
    except KeyError:
        return
    else:
        parts = _split(current_value)
        try:
            index = parts.index(value)
        except ValueError:
            return
        else:
            if len(parts) == 1:
                del os.environ[name]
            else:
                parts.pop(index)
                os.environ[name] = _join(parts)
    #print "popenv", name, value
    return value

class Environment(object):
    '''
    provides attribute-style access to an environment dictionary.

    combined with EnvironmentVariable class, tracks changes to the environment
    '''
#    def __init__(self, environ=None):
#        self.__dict__['environ'] = environ if environ is not None else os.environ
#
#    def __getattr__(self, attr):
#        return EnvironmentVariable(attr, self.environ)

    def __init__(self):
        self.__dict__['_environ'] = defaultdict(list)

    def __getattr__(self, attr):
        if attr.startswith('__') and attr.endswith('__'):
            try:
                self.__dict__[attr]
            except KeyError:
                raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, attr))
        return EnvironmentVariable(attr, self.__dict__['_environ'])

    # There's some code duplication between Environment.__setattr__ and
    # EnvironmentVariable.set... going to leave it as is, assuming it's
    # duplicated for speed reasons... just remember to edit both places
    def __setattr__(self, attr, value):
        if isinstance(value, EnvironmentVariable):
            if value.name == attr:
                # makes no sense to set ourselves. most likely a result of:
                # env.VAR += value
                return
            value = value.value()
        else:
            value = str(value)
        self.__dict__['_environ'][attr] = [setenv(attr, value)]
        
    def __contains__(self, attr):
        return attr in os.environ

    def __str__(self):
        return pprint.pformat(dict(os.environ))

class EnvironmentDict(dict):
    '''
    provides dictionary-style access to an environment.

    combined with EnvironmentVariable class, tracks changes to the environment
    '''
    def __setitem__(self, key, value):
        if isinstance(value, EnvironmentVariable):
            if value.name == key:
                # makes no sense to set ourselves. most likely a result of:
                # env.VAR += value
                return
            value = value.value()
        elif ALL_CAPS.match(key):
            value = str(value)
        dict.__setitem__(self, key, value)

    def __getitem__(self, key):
        # don't error on reference to non-existent env variables
        if ALL_CAPS.match(key):
            return EnvironmentVariable(key, self)
        else:
            return dict.__getitem__(key)

class EnvironmentVariable(object):
    '''
    class representing an environment variable

    combined with Environment class, tracks changes to the environment
    '''

    def __init__(self, name, environ):
        self._name = name
        self._environ = environ

    def __str__(self):
        return '%s = %s' % (self._name, self.value())

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._name)

    def __nonzero__(self):
        return bool(self.value())

    @property
    def name(self):
        return self._name

    def prepend(self, value, **kwargs):
        if isinstance(value, EnvironmentVariable):
            value = value.value()
        expanded_value = prependenv(self._name, value, **kwargs)
        # track changes
        self._environ[self._name].insert(0, expanded_value)

        # update_pypath
        if self.name == 'PYTHONPATH':
            sys.path.insert(0, expanded_value)
        return expanded_value

    def append(self, value, **kwargs):
        if isinstance(value, EnvironmentVariable):
            value = value.value()
        expanded_value = appendenv(self._name, value, **kwargs)
        # track changes
        self._environ[self._name].append(expanded_value)

        # update_pypath
        if self.name == 'PYTHONPATH':
            sys.path.append(expanded_value)
        return expanded_value

    # There's some code duplication between Environment.__setattr__ and
    # EnvironmentVariable.set... going to leave it as is, assuming it's
    # duplicated for speed reasons... just remember to edit both places
    def set(self, value):
        if isinstance(value, EnvironmentVariable):
            value = value.value()
        expanded_value = setenv(self._name, value)
        # track changes
        self._environ[self._name] = [expanded_value]
        return expanded_value

    def setdefault(self, value):
        '''
        set value if the variable does not yet exist
        '''
        if self:
            return self.value()
        else:
            return self.set(value)

    def __add__(self, value):
        '''
        append `value` to this variable's value.

        returns a string
        '''
        if isinstance(value, EnvironmentVariable):
            value = value.value()
        return self.value() + value

    def __iadd__(self, value):
        self.prepend(value)
        return self

    def __eq__(self, value):
        if isinstance(value, EnvironmentVariable):
            value = value.value()
        return self.value() == value

    def __div__(self, value):
        return os.path.join(self.value(), *value.split('/'))

    def value(self):
        return os.environ.get(self._name, None)

    def split(self):
        # FIXME: value could be None.  should we return empty list or raise an error?
        value = self.value()
        if value is not None:
            return _split(value)
        else:
            return []
