# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from rez.utils.sourcecode import SourceCode
from rez.vendor import yaml
from rez.vendor.yaml.dumper import SafeDumper
from rez.vendor.version.version import Version
from rez.vendor.version.requirement import Requirement
from types import FunctionType, BuiltinFunctionType
from inspect import getsourcelines
from textwrap import dedent


class _Dumper(SafeDumper):
    """Dumper which can serialise custom types such as Version, and keeps
    long strings nicely formatted in >/| block-style format.
    """

    def represent_as_str(self, data):
        return self.represent_str(str(data))

    def represent_function(self, data):
        loc = getsourcelines(data)[0][1:]
        code = dedent(''.join(loc))
        return self.represent_str(code)

    def represent_builtin_function(self, data):
        return self.represent_str(str(data))

    def represent_sourcecode(self, data):
        code = data.source
        return self.represent_str(code)


_Dumper.add_representer(str, _Dumper.represent_str)
_Dumper.add_representer(Version, _Dumper.represent_as_str)
_Dumper.add_representer(Requirement, _Dumper.represent_as_str)
_Dumper.add_representer(FunctionType, _Dumper.represent_function)
_Dumper.add_representer(BuiltinFunctionType, _Dumper.represent_builtin_function)
_Dumper.add_representer(SourceCode, _Dumper.represent_sourcecode)


def dump_yaml(data, Dumper=_Dumper, default_flow_style=False):
    """Returns data as yaml-formatted string."""
    content = yaml.dump(data,
                        default_flow_style=default_flow_style,
                        Dumper=Dumper)
    return content.strip()


def load_yaml(filepath):
    """Convenience function for loading yaml-encoded data from disk."""
    with open(filepath) as f:
        txt = f.read()
    return yaml.load(txt, Loader=yaml.FullLoader)


def save_yaml(filepath, **fields):
    """Convenience function for writing yaml-encoded data to disk."""
    content = dump_yaml(fields)
    with open(filepath, 'w') as f:
        f.write(content + '\n')
