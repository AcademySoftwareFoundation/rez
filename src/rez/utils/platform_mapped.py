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


import re


def platform_mapped(func):
    r"""Decorates functions for lookups within a config.platform_map dictionary.

    The first level key is mapped to the func.__name__ of the decorated function.
    Regular expressions are used on the second level key, values.
    Note that there is no guaranteed order within the dictionary evaluation. Only the first matching
    regular expression is being used.
    For example:

    config.platform_map = {
        "os": {
            r"Scientific Linux-(.*)": r"Scientific-\1",    # Scientific Linux-x.x -> Scientific-x.x
            r"Ubuntu-14.\d": r"Ubuntu-14",                 # Any Ubuntu-14.x      -> Ubuntu-14
        },
        "arch": {
            "x86_64": "64bit",                             # Maps both x86_64 and amd64 -> 64bit (don't)
            "amd64": "64bit",
        },
    }
    """
    def inner(*args, **kwargs):

        # Since platform is being used within config lazy import config to prevent
        # circular dependencies
        from rez.config import config

        # Original result
        result = func(*args, **kwargs)

        # The function name is used as primary key
        entry = config.platform_map.get(func.__name__)
        if entry:
            for key, value in entry.items():
                result, changes = re.subn(key, value, result)
                if changes > 0:
                    break

        return result
    return inner
