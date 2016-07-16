name = 'rextest'
version = '1.3'

def commands():
    env.REXTEST_ROOT = '{root}'
    env.REXTEST_VERSION = this.version
    env.REXTEST_MAJOR_VERSION = this.version.major
    # prepend to non-existent var
    env.REXTEST_DIRS.prepend('{root}/data')
    alias('rextest', 'foobar')


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
