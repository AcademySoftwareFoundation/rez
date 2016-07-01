import os
import os.path
from fnmatch import fnmatch
from rez.vendor.argcomplete import CompletionFinder, default_validator, \
    sys_encoding, split_line, debug


class RezCompletionFinder(CompletionFinder):
    def __init__(self, parser, comp_line, comp_point):
        self._parser = parser
        self.always_complete_options = False
        self.exclude = None
        self.validator = default_validator
        self.wordbreaks = " \t\"'@><=;|&(:"  # TODO: might need to be configurable/OS specific

        comp_point = len(comp_line[:comp_point].decode(sys_encoding))
        comp_line = comp_line.decode(sys_encoding)

        cword_prequote, cword_prefix, cword_suffix, comp_words, \
            first_colon_pos = split_line(comp_line, comp_point)

        debug("\nLINE: '{l}'\nPREQUOTE: '{pq}'\nPREFIX: '{p}'".format(l=comp_line, pq=cword_prequote, p=cword_prefix),
              "\nSUFFIX: '{s}'".format(s=cword_suffix),
              "\nWORDS:", comp_words)

        completions = self._get_completions(comp_words, cword_prefix,
                                            cword_prequote, first_colon_pos)
        self.completions = (x.encode(sys_encoding) for x in completions)


def ConfigCompleter(prefix, **kwargs):
    from rez.config import config
    return config.get_completions(prefix)


def PackageCompleter(prefix, **kwargs):
    from rez.packages_ import get_completions
    return get_completions(prefix)


def PackageFamilyCompleter(prefix, **kwargs):
    from rez.packages_ import get_completions
    return get_completions(prefix, family_only=True)


def ExecutablesCompleter(prefix, **kwargs):
    from stat import S_IXUSR, S_IXGRP, S_IXOTH

    paths = os.getenv("PATH", "").split(os.path.pathsep)
    paths = (x for x in paths if x)
    programs = set()

    for path in paths:
        if os.path.isdir(path):
            for name in os.listdir(path):
                if name.startswith(prefix):
                    filepath = os.path.join(path, name)
                    if os.path.isfile(filepath):
                        perms = os.stat(filepath).st_mode
                        if perms & (S_IXUSR | S_IXGRP | S_IXOTH):
                            programs.add(name)
    return programs


class FilesCompleter(object):
    def __init__(self, files=True, dirs=True, file_patterns=None):
        self.files = files
        self.dirs = dirs
        self.file_patterns = file_patterns

    def __call__(self, prefix, **kwargs):
        cwd = os.getcwd()
        abs_ = os.path.isabs(prefix)
        filepath = prefix if abs_ else os.path.join(cwd, prefix)
        n = len(filepath) - len(prefix)
        path, fileprefix = os.path.split(filepath)

        try:
            names = os.listdir(path)
            if not os.path.dirname(prefix):
                names.append(os.curdir)
                names.append(os.pardir)
        except:
            return []

        matching_names = []
        names = (x for x in names if x.startswith(fileprefix))

        for name in names:
            filepath = os.path.join(path, name)
            if os.path.isfile(filepath):
                if not self.files:
                    continue
                if (not self.file_patterns) \
                        or any(fnmatch(name, x) for x in self.file_patterns):
                    matching_names.append(name)
            elif os.path.isdir(filepath):
                matching_names.append(name + os.path.sep)
                if self.dirs:
                    matching_names.append(name)

        if not abs_:
            path = path[n:]
        filepaths = (os.path.join(path, x) for x in matching_names)
        return filepaths


class CombinedCompleter(object):
    def __init__(self, completer, *completers):
        self.completers = [completer]
        self.completers += list(completers)


class AndCompleter(CombinedCompleter):
    def __call__(self, prefix, **kwargs):
        words = set()
        for completer in self.completers:
            words_ = set(completer(prefix, **kwargs))
            words |= words_
        return words


class SequencedCompleter(CombinedCompleter):
    def __init__(self, arg, completer, *completers):
        super(SequencedCompleter, self).__init__(completer, *completers)
        self.arg = arg

    def __call__(self, prefix, **kwargs):
        opts = kwargs.get("parsed_args")
        if opts and hasattr(opts, self.arg):
            value = getattr(opts, self.arg)
            if isinstance(value, list):
                i = len(value)
                try:
                    completer = self.completers[i]
                except:
                    completer = self.completers[-1]
                return completer(prefix, **kwargs)

        return []


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
