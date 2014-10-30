import sys
import re
import pipes


def alias_str(alias, command=None):
    if command is None or command == alias:
        return alias
    else:
        return "%s:%s" % (alias, pipes.quote(command))


def overrides_str(nlevels, levels):
    s = ''
    if isinstance(levels, int):
        levels = [levels]
    for i in range(nlevels):
        if i in levels:
            s += '+'
        else:
            s += '-'
    return '[' + s + ']'


def glob_transform(src_pattern, dest_pattern, txt):
    """Given a pattern such as 'foo*', and another pattern such as '*_foo', and
    a string that matches `src_pattern`, return the expanded second pattern.
    """
    regex_str = '^'
    toks = src_pattern.split('*')
    for i, tok in enumerate(toks):
        regex_str += re.escape(tok)
        if i < len(toks) - 1:
            regex_str += "(?P<_%d>.*)" % i

    regex = re.compile(regex_str + '$')
    m = regex.match(txt)
    assert m
    values = m.groupdict()

    i = 0
    dest = dest_pattern
    while '*' in dest:
        value = values.get("_%d" % i, '')
        dest = dest.replace('*', value, 1)
        i += 1

    return dest


def print_columns(items):
    if not sys.stdout.isatty():
        print '\n'.join(str(x) for x in items)
        return

    try:
        import fcntl, termios, struct
        console_width = struct.unpack('HHHH', \
            fcntl.ioctl(0, termios.TIOCGWINSZ,
                        struct.pack('HHHH', 0, 0, 0, 0)))[1]
    except:
        console_width = 80

    def _w(col):
        return max(len(x) for x in col) + 2

    table = [items]
    prevtable = table
    ncols = 1

    while sum(_w(x) for x in table) < console_width:
        ncols += 1
        n = len(items) / ncols
        if n == 0:
            break
        if len(items) % n:
            n += 1

        prevtable = table
        table = []
        r = items[:]

        while r:
            row = r[:n]
            r = r[n:]
            while len(row) < n:
                row.append('')
            table.append(row)

    tbl = table if sum(_w(x) for x in table) < console_width else prevtable
    widths = [_w(x) for x in tbl]
    for row in zip(*tbl):
        strs = []
        for w,item in zip(widths, row):
            strs.append(item.ljust(w))
        print ''.join(strs)
