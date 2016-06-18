name = 'rextest2'
version = '2'

requires = ["rextest-1.3"]

def commands():
    # prepend to existing var
    env.REXTEST_DIRS.append('{root}/data2')
    setenv("REXTEST2_REXTEST_VER", '{resolve.rextest.version}')
    env.REXTEST2_REXTEST_BASE = resolve.rextest.base


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
