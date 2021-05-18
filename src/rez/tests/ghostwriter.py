
import os
from copy import deepcopy
from rez.utils.sourcecode import _add_decorator, SourceCode, late, include
from rez.serialise import process_python_objects, FileFormat
from rez.vendor.schema.schema import Schema, Optional, Or
from rez.package_serialise import (
    package_serialise_schema,
    package_request_schema,
    package_key_order,
    dump_functions,
)


__version__ = "0.3.2"

__all__ = [
    "DeveloperRepository",
    "early",
    "late",
    "include",
    "building",
]


class DeveloperRepository(object):

    def __init__(self, path):
        """A repository that able to write package.py

        This is meant for unit-testing.

        Example:
            >>> dev_repo = DeveloperRepository("test/dev")
            >>> dev_repo.debug = 1
            >>>
            >>> @early()
            ... def requires():
            ...     return [] if building else ["!bar"]
            ...
            >>> @early()
            ... def variants():
            ...     return [["fun", "os-*"]]
            ...
            >>> @late()
            ... def bar():
            ...     return "cheers"
            ...
            >>> @include("util")
            ... def commands():
            ...     env.PATH.append("{this.root}/bin")
            ...     env.BAR = this.bar
            ...     util.do("stuff")
            ...
            >>> dev_repo.add("foo",
            ...              version="1",
            ...              requires=requires,
            ...              variants=variants,
            ...              bar=bar,
            ...              build_command=False,
            ...              commands=commands)
            # -*- coding: utf-8 -*-
            <BLANKLINE>
            name = 'foo'
            <BLANKLINE>
            version = '1'
            <BLANKLINE>
            @early()
            def requires():
                return [] if building else ["!bar"]
            <BLANKLINE>
            @early()
            def variants():
                return [["fun", "os-*"]]
            <BLANKLINE>
            @include('util')
            def commands():
                env.PATH.append("{this.root}/bin")
                env.BAR = this.bar
                util.do("stuff")
            <BLANKLINE>
            @late()
            def bar():
                return "cheers"
            <BLANKLINE>
            build_command = False
            <BLANKLINE>


        :param path: repository's filesystem path
        """
        self._path = path
        self.debug = None

    @property
    def path(self):
        return self._path

    def add(self, name, **kwargs):
        """Add one developer package into repository

        Generated package.py will be stored just like regular filesystem
        based package, like:

            # versioned
            {repository_root_path}/{pkg-name}/{version}/package.py

            # un-versioned
            {repository_root_path}/{pkg-name}/package.py

        :param name: package name
        :param kwargs: arbitrary package attributes
        :return:
        """
        data = deepcopy(kwargs)
        data["name"] = name

        # process early/late bound functions
        #
        for key, value in data.items():
            if hasattr(value, "_early"):
                data[key] = SourceCode(func=value, eval_as_function=True)
        process_python_objects(data)

        # write out
        #
        pkg_base_path = os.path.join(self._path, name)
        version = data.get("version")
        if version and isinstance(version, str):
            pkg_base_path = os.path.join(pkg_base_path, version)

        if not os.path.isdir(pkg_base_path):
            os.makedirs(pkg_base_path)
        filepath = os.path.join(pkg_base_path, "package.py")
        with open(filepath, "w") as f:
            dump_developer_package_data(data, buf=f, format_=FileFormat.py)

        # For debug
        #
        if self.debug:
            with open(filepath, "r") as f:
                print(f.read())


def early():
    """Decorator for marking function as package's 'early' bound attribute
    """
    def decorated(fn):
        setattr(fn, "_early", True)
        _add_decorator(fn, "early")
        return fn

    return decorated


# Lint helper

building = None


# Vendor

def dump_developer_package_data(data,
                                buf,
                                format_=FileFormat.py,
                                skip_attributes=None):
    """Write developer package data to `buf`.

    Modified from rez for supporting dump early bound `variants`.

    Args:
        data (dict): Data source - must conform to `package_serialise_schema`.
        buf (file-like object): Destination stream.
        format_ (`FileFormat`): Format to dump data in.
        skip_attributes (list of str): List of attributes to not print.
    """
    if format_ == FileFormat.txt:
        raise ValueError("'txt' format not supported for packages.")

    data_ = dict((k, v) for k, v in data.items() if v is not None)
    data_ = developer_serialise_schema.validate(data_)  # variant can be early
    skip = set(skip_attributes or [])

    items = []
    for key in package_key_order:
        if key not in skip:
            value = data_.pop(key, None)
            if value is not None:
                items.append((key, value))

    # remaining are arbitrary keys
    for key, value in data_.items():
        if key not in skip:
            items.append((key, value))

    dump_func = dump_functions[format_]
    dump_func(items, buf)


def early_bound(schema):
    return Or(SourceCode, schema)


_schema_dict = package_serialise_schema._schema.copy()
_schema_dict[Optional("variants")] = early_bound([[package_request_schema]])

developer_serialise_schema = Schema(_schema_dict)


# MIT License
#
# Copyright (c) 2021 David Lai
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
