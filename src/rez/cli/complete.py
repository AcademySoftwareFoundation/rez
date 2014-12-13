"""
Prints package completion strings.
"""
from rez.vendor import argparse


__doc__ = argparse.SUPPRESS


def setup_parser(parser, completions=False):
    pass


def command(opts, parser, extra_arg_groups=None):
    from rez.cli._util import subcommands, hidden_subcommands
    import os
    import re

    # get comp info from environment variables
    comp_line = os.getenv("COMP_LINE", "")
    comp_point = os.getenv("COMP_POINT", "")
    try:
        comp_point = int(comp_point)
    except:
        comp_point = len(comp_line)

    last_word = comp_line.split()[-1]
    if comp_line.endswith(last_word):
        prefix = last_word
    else:
        prefix = None

    def _pop_arg(l, p):
        words = l.split()
        arg = None
        if words:
            arg = words[0]
            l_ = l.lstrip()
            p -= (len(l) - len(l_) + len(arg))
            l = l_[len(arg):]
            return l, p, arg
        return l, p, arg

    # determine subcommand, possibly give subcommand completion
    subcommand = None
    comp_line, comp_point, cmd = _pop_arg(comp_line, comp_point)
    if cmd in ("rez", "rezolve"):
        comp_line, comp_point, arg = _pop_arg(comp_line, comp_point)
        if arg:
            if prefix != arg:
                subcommand = arg
    else:
        subcommand = cmd.split("-", 1)[-1]

    if subcommand is None:
        cmds = set(subcommands) - set(hidden_subcommands)
        if prefix:
            cmds = (x for x in cmds if x.startswith(prefix))
        print " ".join(cmds)

    if subcommand not in subcommands:
        return

    # replace '--' with special '--N#' flag so that subcommands can specify
    # custom completions.
    regex = re.compile("\s--\s")
    ddashes = regex.findall(comp_line)
    for i, ddash in enumerate(ddashes):
        j = comp_line.find(ddash)
        while comp_line[j] != "-":
            j += 1
        j += 2
        s = "N%d" % i
        comp_line = comp_line[:j] + s + comp_line[j:]
        if comp_point >= j:
            comp_point += len(s)

    # create parser for subcommand
    from rez.backport.importlib import import_module
    module_name = "rez.cli.%s" % subcommand
    mod = import_module(module_name)
    parser = argparse.ArgumentParser()
    mod.setup_parser(parser, completions=True)

    # have to massage input a little so argcomplete behaves
    cmd = "rez-%s" % subcommand
    comp_line = cmd + comp_line
    comp_point += len(cmd)

    # generate the completions
    from rez.cli._complete_util import RezCompletionFinder
    completer = RezCompletionFinder(parser=parser,
                                    comp_line=comp_line,
                                    comp_point=comp_point)
    words = completer.completions
    print ' '.join(words)
