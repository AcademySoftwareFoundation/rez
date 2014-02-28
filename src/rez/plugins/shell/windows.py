from rez import plugin_factory
from rez.shells import Shell



# FIMXE: this is not in working order!!! It is only here for reference
class WinShell(Shell):
    @classmethod
    def name(cls):
        return 'windows'

    # These are variables where windows will construct the value from the value
    # from system + user + volatile environment values (in that order)
    WIN_PATH_VARS = ('PATH', 'LibPath', 'Os2LibPath')

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
