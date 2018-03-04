"""
Generates the RestructuredText 'README' file from the markdown 'README.md' file.
Be careful: it isn't foolproof, use of fancier markdown features will probably
break it. The README file is used by Pypi to create the Rez frontpage.
"""
from __future__ import print_function, with_statement

import os.path


if __name__ == "__main__":
    build_utils_path = os.path.dirname(__file__)
    src_path = os.path.dirname(build_utils_path)
    source_path = os.path.dirname(src_path)

    readme_md = os.path.join(source_path, "README.md")
    with open(readme_md) as f:
        content = f.read().strip()

    lines = content.split('\n')
    currln = None
    dest = []

    def _flushln():
        global currln
        if currln is not None:
            dest.append(currln)
            currln = None

    # remove line wraps
    for ln in lines:
        if (ln == '') or ln.startswith('    ') or ln.startswith('#') \
                or ln.startswith('* '):
            _flushln()

        if (ln == '') or ln.startswith('    ') or ln.startswith('#'):
            dest.append(ln)
        else:
            if currln is None:
                currln = ln
            else:
                currln += ' ' + ln.strip()

    _flushln()
    lines = dest
    dest = []
    prev = None
    curr = None

    # reformat lines
    for ln in lines:
        prev = curr
        curr = None
        toks = ln.split()

        if (ln == ''):
            if prev == 'code':
                dest.append('    ')
                curr = 'code'
            else:
                dest.append('')
        elif ln.startswith('#'):
            title = ' '.join(toks[1:])
            dest.append(title)
            dest.append('-' * len(title))
        elif toks and toks[0] == '*':
            line = '- ' + ln[1:]
            dest.append(line)
        elif ln.startswith('    '):
            if prev == 'code':
                dest.append(ln)
            else:
                dest.append('::')
                dest.append('')
                dest.append(ln)
            curr = 'code'
        else:
            dest.append(ln)

    # done
    dest.append('')
    readme = os.path.join(source_path, "README")
    with open(readme, 'w') as f:
        f.write('\n'.join(dest))

    print("README was written")
