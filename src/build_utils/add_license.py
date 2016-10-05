"""
Adds LGPL and Copyright notice to the end of each .py file. You need to run
this script from the src/ subdirectory of the rez source.
"""
import os
import os.path
from datetime import datetime


notice = \
"""
Copyright 2013-{year} {authors}.

This library is free software: you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library.  If not, see <http://www.gnu.org/licenses/>.
"""

year = datetime.now().year


skip_dirs = [
    "vendor",
    "build_utils",
    "backport"
]


def extract_copyright_authors(txt):
    lines = txt.split('\n')
    for line in lines:
        if line.startswith("# Copyright"):
            if str(year) in line:
                part = line.split(str(year))[-1]
            elif str(year - 1) in line:
                part = line.split(str(year - 1))[-1]
            else:
                return []

            parts = part.strip().rstrip('.').split(',')
            authors = []

            for part in parts:
                auth = part.strip()
                if auth != "Allan Johns":
                    authors.append(auth)

            return authors

    return []


if __name__ == "__main__":
    filepaths = []

    notice_lines = notice.strip().split('\n')
    notice_lines = [("# %s" % x).rstrip() for x in notice_lines]
    copyright_line = notice_lines[0]
    notice_lines = notice_lines[1:]

    # find py files
    for root, dirs, names in os.walk('.'):
        for name in names:
            if name.endswith(".py"):
                filepath = os.path.join(root, name)
                print "found: %s" % filepath
                filepaths.append(filepath)

        for dirname in skip_dirs:
            if dirname in dirs:
                dirs.remove(dirname)

    # append notice to each py file
    for filepath in filepaths:
        with open(filepath) as f:
            txt = f.read()

        lines = txt.split('\n')

        while lines and not lines[-1].strip():
            lines.pop()

        while lines and lines[-1].startswith('#'):
            lines.pop()

        while lines and not lines[-1].strip():
            lines.pop()

        lines.append('')
        lines.append('')

        authors = extract_copyright_authors(txt)
        authors = ["Allan Johns"] + authors

        copyright_line_ = copyright_line.format(
            year=year, authors=", ".join(authors))

        lines.append(copyright_line_)
        lines.extend(notice_lines)
        lines.append('')

        new_txt = '\n'.join(lines)

        print "Writing updated %s..." % filepath
        with open(filepath, 'w') as f:
            f.write(new_txt)
