name = 'anti'
version = '1.0.0'
authors = ["joe.bloggs"]
uuid = "e760fa04-043d-47bb-ba4d-543b18a70959"
description = "package with anti package"


private_build_requires = ["build_util"]
requires = ["floob", "!loco"]

def commands():
    env.PYTHONPATH.append('{root}/python')

build_command = 'python {root}/build.py {install}'


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
