
# make sure imported modules don't break package installs
import os

name = 'floob'
version = '1.2.0'
authors = ["joe.bloggs"]
uuid = "156730d7122441e3a5745cc81361f49a"
description = "floobtasticator"

private_build_requires = ["build_util"]

def commands():
    env.PYTHONPATH.append('{root}/python')


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
