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


from itertools import groupby


class VersionError(Exception):
    pass


class ParseException(Exception):
    pass


class _Common(object):
    def __str__(self):
        raise NotImplementedError

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, str(self))


def dedup(iterable):
    """Removes duplicates from a sorted sequence."""
    for e in groupby(iterable):
        yield e[0]
