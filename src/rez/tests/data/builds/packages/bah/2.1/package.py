name = 'bah'
version = '2.1'
authors = ["joe.bloggs"]
uuid = "3c027ce6593244af947e305fc48eec96"
description = "bah humbug"

private_build_requires = ["build_util"]

variants = [
    ["foo-1.0"],
    ["foo-1.1"]]

hashed_variants = True

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
