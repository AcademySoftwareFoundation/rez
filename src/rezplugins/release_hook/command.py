"""
Executes pre- and post-release shell commands
"""
from __future__ import print_function

import getpass
import sys
import os
from subprocess import Popen, PIPE, STDOUT

from rez.release_hook import ReleaseHook
from rez.exceptions import ReleaseHookCancellingError
from rez.config import config
from rez.system import system
from rez.utils.logging_ import print_debug
from rez.utils.scope import scoped_formatter
from rez.utils.formatting import expandvars
from rez.vendor.schema.schema import Schema, Or, Optional, Use, And
from rez.vendor.six import six
from rez.util import which


basestring = six.string_types[0]


class CommandReleaseHook(ReleaseHook):

    commands_schema = Schema({
        "command": basestring,
        Optional("args"): Or(
            And(
                basestring,
                Use(lambda x: x.strip().split())
            ),
            [basestring]
        ),
        Optional("pretty_args"): bool,
        Optional("user"): basestring,
        Optional("env"): dict
    })

    schema_dict = {
        "print_commands": bool,
        "print_output": bool,
        "print_error": bool,
        "cancel_on_error": bool,
        "stop_on_error": bool,
        "pre_build_commands": [commands_schema],
        "pre_release_commands": [commands_schema],
        "post_release_commands": [commands_schema]
    }

    @classmethod
    def name(cls):
        return "command"

    def __init__(self, source_path):
        super(CommandReleaseHook, self).__init__(source_path)

    def execute_command(self, cmd_name, cmd_arguments, user, errors, env=None):
        def _err(msg):
            errors.append(msg)
            if self.settings.print_error:
                print(msg, file=sys.stderr)

        kwargs = {}
        if env:
            kwargs["env"] = env

        def _execute(commands):
            process = Popen(commands, stdout=PIPE, stderr=STDOUT, **kwargs)
            stdout, _ = process.communicate()

            if process.returncode != 0:
                msg = "command failed:\n%s" % stdout
                _err(msg)
                return False
            if self.settings.print_output:
                print(stdout.strip())
            return True

        if not os.path.isfile(cmd_name):
            cmd_full_path = which(cmd_name)
        else:
            cmd_full_path = cmd_name
        if not cmd_full_path:
            msg = "%s: command not found" % cmd_name
            _err(msg)
            return False

        cmds = [cmd_full_path] + (cmd_arguments or [])
        if user == 'root':
            cmds = ['sudo'] + cmds
            return _execute(cmds)
        elif user and user != getpass.getuser():
            raise NotImplementedError  # TODO
        else:
            return _execute(cmds)

    def pre_build(self, user, install_path, variants=None, **kwargs):
        errors = []
        self._execute_commands(self.settings.pre_build_commands,
                               install_path=install_path,
                               package=self.package,
                               errors=errors,
                               variants=variants)

        if errors and self.settings.cancel_on_error:
            raise ReleaseHookCancellingError(
                "The following pre-build commands failed:\n%s"
                % '\n\n'.join(errors))

    def pre_release(self, user, install_path, variants=None, **kwargs):
        errors = []
        self._execute_commands(self.settings.pre_release_commands,
                               install_path=install_path,
                               package=self.package,
                               errors=errors,
                               variants=variants)

        if errors and self.settings.cancel_on_error:
            raise ReleaseHookCancellingError(
                "The following pre-release commands failed:\n%s"
                % '\n\n'.join(errors))

    def post_release(self, user, install_path, variants, **kwargs):
        # note that the package we use here is the *installed* package, not the
        # developer package (self.package). Otherwise, attributes such as 'root'
        # will be None
        errors = []
        if variants:
            package = variants[0].parent
        else:
            package = self.package

        self._execute_commands(self.settings.post_release_commands,
                               install_path=install_path,
                               package=package,
                               errors=errors,
                               variants=variants)
        if errors:
            print_debug(
                "The following post-release commands failed:\n"
                + '\n\n'.join(errors)
            )

    def _execute_commands(self, commands, install_path, package, errors=None,
                          variants=None):
        release_dict = dict(path=install_path)
        variant_infos = []
        if variants:
            for variant in variants:
                if isinstance(variant, six.integer_types):
                    variant_infos.append(variant)
                else:
                    package = variant.parent
                    var_dict = dict(variant.resource.variables)
                    # using '%s' will preserve potential str/unicode nature
                    var_dict['variant_requires'] = ['%s' % x
                                                    for x in variant.resource.variant_requires]
                    variant_infos.append(var_dict)
        formatter = scoped_formatter(system=system,
                                     release=release_dict,
                                     package=package,
                                     variants=variant_infos,
                                     num_variants=len(variant_infos))

        for conf in commands:
            program = conf["command"]

            env_ = None
            env = conf.get("env")
            if env:
                env_ = os.environ.copy()
                env_.update(env)

            # If we have, ie, a list, and format_pretty is True, it will be printed
            # as "1 2 3" instead of "[1, 2, 3]"
            formatter.__dict__['format_pretty'] = conf.get(
                "pretty_args", True)

            args = conf.get("args", [])
            args = [formatter.format(x) for x in args]
            args = [expandvars(x, environ=env_) for x in args]

            if self.settings.print_commands or config.debug("package_release"):
                from subprocess import list2cmdline
                toks = [program] + args

                msgs = []
                msgs.append("running command: %s" % list2cmdline(toks))
                if env:
                    for key, value in env.items():
                        msgs.append("    with: %s=%s" % (key, value))

                if self.settings.print_commands:
                    print('\n'.join(msgs))
                else:
                    for msg in msgs:
                        print_debug(msg)

            if not self.execute_command(cmd_name=program,
                                        cmd_arguments=args,
                                        user=conf.get("user"),
                                        errors=errors,
                                        env=env_):
                if self.settings.stop_on_error:
                    return


def register_plugin():
    return CommandReleaseHook


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
