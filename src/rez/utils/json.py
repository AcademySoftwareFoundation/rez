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


from __future__ import absolute_import
import json
from json import dumps  # noqa (forwarded)
import sys


if sys.version_info.major >= 3:

    def loads(data):
        return json.loads(data)

# py2
else:

    def loads(json_text):
        """Avoids returning unicodes in py2.

        https://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-from-json
        """
        def _byteify(input, ignore_dicts=False):
            if isinstance(input, list):
                return [_byteify(x) for x in input]
            elif isinstance(input, unicode):
                try:
                    return str(input)
                except UnicodeEncodeError:
                    return input
            elif isinstance(input, dict) and not ignore_dicts:
                return {
                    _byteify(k, ignore_dicts=True): _byteify(v, True)
                    for k, v in input.items()
                }
            else:
                return input

        return _byteify(json.loads(json_text, object_hook=_byteify))
