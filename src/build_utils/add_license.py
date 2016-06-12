"""
Adds LGPL and Copyright notice to the end of each .py file. You need to run
this script from the src/ subdirectory of the rez source.
"""
import os
import os.path


notice = \
"""
Copyright 2016 Allan Johns.

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

skip_dirs = [
    "vendor",
    "build_utils",
    "backport"
]


if __name__ == "__main__":
    filepaths = []

    notice_lines = notice.strip().split('\n')
    notice_lines = [("# %s" % x) for x in notice_lines]

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
        lines.extend(notice_lines)
        lines.append('')

        new_txt = '\n'.join(lines)

        print "Writing updated %s..." % filepath
        with open(filepath, 'w') as f:
            f.write(new_txt)
