"""
Utility code for supporting earlier Rez data in later Rez releases.
"""
import re
import os
import os.path
import textwrap


variant_key_conversions = {
    "name": "name",
    "version": "version",
    "index": "index",
    "search_path": "location"
}


def convert_old_variant_handle(handle_dict):
    """Convert a variant handle from serialize_version < 4.0."""
    old_variables = handle_dict.get("variables", {})
    variables = dict(repository_type="filesystem")

    for old_key, key in variant_key_conversions.items():
        value = old_variables.get(old_key)
        variables[key] = value

    path = handle_dict["path"]
    filename = os.path.basename(path)
    if os.path.splitext(filename)[0] == "package":
        key = "filesystem.variant"
    else:
        key = "filesystem.variant.combined"

    return dict(key=key, variables=variables)


def convert_old_command_expansions(command):
    """Convert expansions from !OLD! style to {new}."""
    command = command.replace("!VERSION!", "{version}")
    command = command.replace("!MAJOR_VERSION!", "{version.major}")
    command = command.replace("!MINOR_VERSION!", "{version.minor}")
    command = command.replace("!BASE!", "{base}")
    command = command.replace("!ROOT!", "{root}")
    command = command.replace("!USER!", "{system.user}")
    return command


within_unescaped_quotes_regex = re.compile('(?<!\\\\)"(.*?)(?<!\\\\)"')


def convert_old_commands(commands, annotate=True):
    """Converts old-style package commands into equivalent Rex code."""
    from rez.config import config
    from rez.utils.logging_ import print_debug

    def _repl(s):
        return s.replace('\\"', '"')

    def _encode(s):
        # this replaces all occurrances of '\"' with '"', *except* for those
        # occurrances of '\"' that are within double quotes, which themselves
        # are not escaped. In other words, the string:
        # 'hey "there \"you\" " \"dude\" '
        # ..will convert to:
        # 'hey "there \"you\" " "dude" '
        s_new = ''
        prev_i = 0

        for m in within_unescaped_quotes_regex.finditer(s):
            s_ = s[prev_i:m.start()]
            s_new += _repl(s_)

            s_new += s[m.start():m.end()]
            prev_i = m.end()

        s_ = s[prev_i:]
        s_new += _repl(s_)
        return repr(s_new)

    loc = []

    for cmd in commands:
        if annotate:
            txt = "OLD COMMAND: %s" % cmd
            line = "comment(%s)" % _encode(txt)
            loc.append(line)

        cmd = convert_old_command_expansions(cmd)
        toks = cmd.strip().split()

        try:
            if toks[0] == "export":
                var, value = cmd.split(' ', 1)[1].split('=', 1)
                for bookend in ('"', "'"):
                    if value.startswith(bookend) and value.endswith(bookend):
                        value = value[1:-1]
                        break

                # As the only old-style commands were Linux/Bash based,
                # we assume using the default separator ":" is ok - we don't
                # need to use os.pathsep as we don't expected to see a
                # Windows path here.
                separator = config.env_var_separators.get(var, ":")

                # This is a special case.  We don't want to include "';'" in
                # our env var separators map as it's not really the correct
                # behaviour/something we want to promote.  It's included here for
                # backwards compatibility only, and to not propogate elsewhere.
                if var == "CMAKE_MODULE_PATH":
                    value = value.replace("'%s'" % separator, separator)
                    value = value.replace('"%s"' % separator, separator)
                    value = value.replace(":", separator)

                parts = value.split(separator)
                parts = [x for x in parts if x]
                if len(parts) > 1:
                    idx = None
                    var1 = "$%s" % var
                    var2 = "${%s}" % var
                    if var1 in parts:
                        idx = parts.index(var1)
                    elif var2 in parts:
                        idx = parts.index(var2)
                    if idx in (0, len(parts) - 1):
                        func = "appendenv" if idx == 0 else "prependenv"
                        parts = parts[1:] if idx == 0 else parts[:-1]
                        val = separator.join(parts)
                        loc.append("%s('%s', %s)" % (func, var, _encode(val)))
                        continue

                loc.append("setenv('%s', %s)" % (var, _encode(value)))
            elif toks[0].startswith('#'):
                loc.append("comment(%s)" % _encode(' '.join(toks[1:])))
            elif toks[0] == "alias":
                match = re.search("alias (?P<key>.*?)=(?P<value>.*)", cmd)
                key = match.groupdict()['key'].strip()
                value = match.groupdict()['value'].strip()
                if (value.startswith('"') and value.endswith('"')) or \
                        (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                loc.append("alias('%s', %s)" % (key, _encode(value)))
            else:
                # assume we can execute this as a straight command
                loc.append("command(%s)" % _encode(cmd))
        except:
            # if anything goes wrong, just fall back to bash command
            loc.append("command(%s)" % _encode(cmd))

    rex_code = '\n'.join(loc)
    if config.debug("old_commands"):
        br = '-' * 80
        msg = textwrap.dedent(
            """
            %s
            OLD COMMANDS:
            %s

            NEW COMMANDS:
            %s
            %s
            """) % (br, '\n'.join(commands), rex_code, br)
        print_debug(msg)
    return rex_code


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
