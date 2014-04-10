'''
Display a list of available tools and the packages that provide them.
'''

def setup_parser(parser):
    pass

def command(opts):
    from rez.env import get_tools
    from rez.util import columnise
    import sys

    entries = get_tools()
    if not entries:
        print >> sys.stderr, "No tools available."
        sys.exit(0)

    is_wraps = (set(x[2] for x in entries) != set([None]))
    if is_wraps:
        rows = [["TOOL", "PACKAGE", "CONTEXT"],
                ["----", "-------", "-------"]]
    else:
        rows = [["TOOL", "PACKAGE", ''],
                ["----", "-------", '']]

    for tool, pkg, rxt in entries:
        rows.append([tool, pkg, rxt or ''])

    print '\n'.join(columnise(rows))
    print
