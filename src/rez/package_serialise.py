from __future__ import print_function
from rez.vendor import yaml
from rez.serialise import FileFormat
from rez.package_resources_ import help_schema, late_bound
from rez.vendor.schema.schema import Schema, Optional, And, Or, Use
from rez.vendor.version.version import Version
from rez.vendor.six import six
from rez.utils.sourcecode import SourceCode
from rez.utils.formatting import PackageRequest, indent, \
    dict_to_attributes_code, as_block_string
from rez.utils.schema import Required
from rez.utils.yaml import dump_yaml
from pprint import pformat

# Backwards compatibility with Python 2
basestring = six.string_types[0]


# preferred order of keys in a package definition file
package_key_order = [
    'name',
    'version',
    'description',
    'authors',
    'tools',
    'has_plugins',
    'plugin_for',
    'requires',
    'build_requires',
    'private_build_requires',
    'variants',
    'commands',
    'pre_commands',
    'post_commands',
    'help',
    'config',
    'uuid',
    'timestamp',
    'release_message',
    'changelog',
    'vcs',
    'revision',
    'previous_version',
    'previous_revision']


version_schema = Or(basestring, And(Version, Use(str)))

package_request_schema = Or(basestring, And(PackageRequest, Use(str)))

source_code_schema = Or(SourceCode, And(basestring, Use(SourceCode)))

tests_schema = Schema({
    Optional(basestring): Or(
        Or(basestring, [basestring]),
        {
            "command": Or(basestring, [basestring]),
            Optional("requires"): [package_request_schema]
        }
    )
})


# package serialisation schema
package_serialise_schema = Schema({
    Required("name"):                   basestring,
    Optional("version"):                version_schema,
    Optional("description"):            basestring,
    Optional("authors"):                [basestring],
    Optional("tools"):                  late_bound([basestring]),

    Optional('requires'):               late_bound([package_request_schema]),
    Optional('build_requires'):         late_bound([package_request_schema]),
    Optional('private_build_requires'): late_bound([package_request_schema]),

    Optional('variants'):               [[package_request_schema]],

    Optional('relocatable'):            late_bound(Or(None, bool)),
    Optional('hashed_variants'):        bool,

    Optional('pre_commands'):           source_code_schema,
    Optional('commands'):               source_code_schema,
    Optional('post_commands'):          source_code_schema,

    Optional("help"):                   late_bound(help_schema),
    Optional("uuid"):                   basestring,
    Optional("config"):                 dict,

    Optional('tests'):                  late_bound(tests_schema),

    Optional("timestamp"):              int,
    Optional('revision'):               object,
    Optional('changelog'):              basestring,
    Optional('release_message'):        Or(None, basestring),
    Optional('previous_version'):       version_schema,
    Optional('previous_revision'):      object,

    Optional(basestring):               object
})


def dump_package_data(data, buf, format_=FileFormat.py, skip_attributes=None):
    """Write package data to `buf`.

    Args:
        data (dict): Data source - must conform to `package_serialise_schema`.
        buf (file-like object): Destination stream.
        format_ (`FileFormat`): Format to dump data in.
        skip_attributes (list of str): List of attributes to not print.
    """
    if format_ == FileFormat.txt:
        raise ValueError("'txt' format not supported for packages.")

    data_ = dict((k, v) for k, v in data.items() if v is not None)
    data_ = package_serialise_schema.validate(data_)
    skip = set(skip_attributes or [])

    items = []
    for key in package_key_order:
        if key not in skip:
            value = data_.pop(key, None)
            if value is not None:
                items.append((key, value))

    # remaining are arbitrary keys
    for key, value in data_.items():
        if key not in skip:
            items.append((key, value))

    dump_func = dump_functions[format_]
    dump_func(items, buf)


# Keeping annotations as rex 'comment' actions is only useful when a package's
# old commands are being converted on the fly - in this case, the new commands
# are never written to disk, so the only way to be able to debug new/old commands
# is to see them in the context. But here we are writing packages to disk, so
# instead we just comment out these comment actions - that way we can refer to
# the package file to see what the original commands were, but they don't get
# processed by rex.
#
def _commented_old_command_annotations(sourcecode):
    lines = sourcecode.source.split('\n')
    for i, line in enumerate(lines):
        if line.startswith("comment('OLD COMMAND:"):
            lines[i] = "# " + line
    source = '\n'.join(lines)

    other = sourcecode.copy()
    other.source = source
    return other


def _dump_package_data_yaml(items, buf):
    for i, (key, value) in enumerate(items):
        if isinstance(value, SourceCode) \
                and key in ("commands", "pre_commands", "post_commands"):
            value = _commented_old_command_annotations(value)

        d = {key: value}
        txt = dump_yaml(d)
        print(txt, file=buf)
        if i < len(items) - 1:
            print('', file=buf)


def _dump_package_data_py(items, buf):
    print("# -*- coding: utf-8 -*-\n", file=buf)

    for i, (key, value) in enumerate(items):
        if key in ("description", "changelog") and len(value) > 40:
            # a block-comment style, triple-quoted string
            block_str = as_block_string(value)
            txt = "%s = \\\n%s" % (key, indent(block_str))
        elif key == "config":
            # config is a scope
            attrs_txt = dict_to_attributes_code(dict(config=value))
            txt = "with scope('config') as config:\n%s" % indent(attrs_txt)
        elif isinstance(value, SourceCode):
            # source code becomes a python function
            if key in ("commands", "pre_commands", "post_commands"):
                value = _commented_old_command_annotations(value)

            txt = value.to_text(funcname=key)
        elif isinstance(value, list) and len(value) > 1:
            # nice formatting for lists
            lines = ["%s = [" % key]
            for j, entry in enumerate(value):
                entry_txt = pformat(entry)
                entry_lines = entry_txt.split('\n')
                for k, line in enumerate(entry_lines):
                    if j < len(value) - 1 and k == len(entry_lines) - 1:
                        line = line + ","
                    lines.append("    " + line)
            lines.append("]")
            txt = '\n'.join(lines)
        else:
            # default serialisation
            value_txt = pformat(value)
            if '\n' in value_txt:
                txt = "%s = \\\n%s" % (key, indent(value_txt))
            else:
                txt = "%s = %s" % (key, value_txt)

        print(txt, file=buf)
        if i < len(items) - 1:
            print('', file=buf)


dump_functions = {FileFormat.py: _dump_package_data_py,
                  FileFormat.yaml: _dump_package_data_yaml}


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
