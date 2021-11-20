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


"""
TCSH shell
"""
from rez.utils.platform_ import platform_
from rezplugins.shell.csh import CSH
from rez import module_root_path
from rez.rex import EscapedString
import os.path
import pipes


class TCSH(CSH):

    @classmethod
    def name(cls):
        return 'tcsh'

    def escape_string(self, value):
        value = EscapedString.promote(value)
        value = value.expanduser()
        result = ''

        for is_literal, txt in value.strings:
            if is_literal:
                txt = pipes.quote(txt)
                if not txt.startswith("'"):
                    txt = "'%s'" % txt
            else:
                txt = txt.replace('"', '"\\""')
                txt = txt.replace('!', '\\!')
                txt = '"%s"' % txt
            result += txt
        return result

    def _bind_interactive_rez(self):
        super(TCSH, self)._bind_interactive_rez()
        completion = os.path.join(module_root_path, "completion", "complete.csh")
        self.source(completion)


def register_plugin():
    if platform_.name != "windows":
        return TCSH
