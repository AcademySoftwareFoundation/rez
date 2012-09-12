"""
Functions for parsing rez parenthesised syntax, used to create subshells on the fly (see the comments
in bin/rez-env-autowrappers_.py)
"""

import pyparsing as pp



# split pkgs string into separate subshells
base_pkgs = None
subshells = None
curr_ss = None
merged_base_pkgs = None
merged_subshells = None

def parse_request(s):
    """
    Parses any request string, including parenthesised form, and merging (pipe operator).
    @return (base_pkgs, subshells). base_pkgs is a list of packages in the 'master' shell, ie 
        outside of any parenthesised subshell. 'subshells' is a dict of subshells, keyed on the
        subshell name.
    """

    global base_pkgs
    global subshells
    global curr_ss
    global merged_base_pkgs
    global merged_subshells

    base_pkgs = []
    subshells = {}
    merged_base_pkgs = []
    merged_subshells = {}
    curr_ss = None

    def _parse_pkg(s, loc, toks):
        global curr_ss
        pkg_str = str('').join(toks)
        if curr_ss is None:
            base_pkgs.append(pkg_str)
        else:
            curr_ss["pkgs"].append(pkg_str)

    def _parse_ss_label(s, loc, toks):
        curr_ss["label"] = toks[0]

    def _parse_ss_prefix(s, loc, toks):
        global curr_ss
        curr_ss = {
            "pkgs": [],
            "prefix": '',
            "suffix": ''
        }
        prefix_str = toks[0][:-1]
        if prefix_str:
            curr_ss["prefix"] = prefix_str

    def _parse_ss_suffix(s, loc, toks):
        global curr_ss
        suffix_str = toks[0][1:]
        if suffix_str:
            curr_ss["suffix"] = suffix_str
        if "label" not in curr_ss:
            pkg_fam = curr_ss["pkgs"][0].split('-')[0]
            label_str = curr_ss["prefix"] + pkg_fam + curr_ss["suffix"]
            curr_ss["label"] = label_str

        subshell_name = curr_ss["label"]
        if subshell_name in subshells:
            print >> sys.stderr, "Error: subshell '%s' is defined more than once!" % subshell_name
            sys.exit(1)

        subshells[subshell_name] = curr_ss
        curr_ss = None

    def _parse_ss_request(s, loc, toks):
        global base_pkgs
        global subshells
        global merged_base_pkgs
        global merged_subshells
        merged_base_pkgs = _merge_pkgs(merged_base_pkgs, base_pkgs)
        merged_subshells = _merge_subshells(merged_subshells, subshells)
        base_pkgs = []
        subshells = {}        

    _pkg = pp.Regex("[a-zA-Z_0-9~<=^\\.\\-\\!\\+]+").setParseAction(_parse_pkg)

    _subshell_label = pp.Regex("[a-zA-Z0-9_]+")
    _subshell_label_decl = (_subshell_label + ':').setParseAction(_parse_ss_label)
    _subshell_body = (_subshell_label_decl * (0,1)) + pp.OneOrMore(_pkg)
    _subshell_prefix = (pp.Regex("[a-zA-Z0-9_]+\\(") ^ '(').setParseAction(_parse_ss_prefix)
    _subshell_suffix = (pp.Regex("\\)[a-zA-Z0-9_]+") ^ ')').setParseAction(_parse_ss_suffix)
    _subshell = _subshell_prefix + _subshell_body + _subshell_suffix

    _request = pp.OneOrMore(_pkg ^ _subshell).setParseAction(_parse_ss_request)
    _expr = _request + pp.ZeroOrMore('|' + _request)

    pr = _expr.parseString(s, parseAll=True)
    return (merged_base_pkgs, merged_subshells)


def _merge_pkgs(pkgs, override_pkgs):

    def _parse_pkg(pkg):
        rm = pkg.startswith('^')
        if rm:
            if len(pkg.split('-')) > 1:
                raise Exception("Only unversioned package allowed with the remove operator '^'")
            pkg = pkg[1:]
        return (pkg.split('-')[0], rm)

    merged_pkgs = []
    override_pkgs2 = override_pkgs[:]

    opkgs = {}
    for pkg in override_pkgs:
        name,rm = _parse_pkg(pkg)
        opkgs[name] = (pkg,rm)

    for pkg in pkgs:
        name,rm = _parse_pkg(pkg)
        opkg = opkgs.get(name)
        if opkg:
            if not opkg[1]:
                merged_pkgs.append(opkg[0])
            override_pkgs2.remove(opkg[0])
        else:
            merged_pkgs.append(pkg)

    merged_pkgs.extend(override_pkgs2)
    return merged_pkgs


def _merge_subshells(subshells, override_subshells):

    merged_subshells = {}
    override_subshells2 = override_subshells.copy()

    for name,ss in subshells.iteritems():
        oss = override_subshells.get(name)
        if oss:
            merged_pkgs = _merge_pkgs(ss["pkgs"], oss["pkgs"])
            new_ss = ss.copy()
            new_ss.update(oss)
            new_ss["pkgs"] = merged_pkgs
            merged_subshells[name] = new_ss
            del override_subshells2[name]
        else:
            merged_subshells[name] = ss

    merged_subshells.update(override_subshells2)
    return merged_subshells


def encode_request(base_pkgs, subshells):
    """
    Take base packages and subshells (that parse_request() generates), and re-encode back into
        a string. Returns this string.
    """
    toks = base_pkgs[:]
    for ss in subshells.itervalues():
        toks.append(_encode_subshell(ss))
    return str(' ').join(toks)


def _encode_subshell(ss):
    s = ''
    prefix = ss.get("prefix") or ''
    s += prefix

    s += '(%s: ' % ss["label"]
    s += str(' ').join(ss["pkgs"])

    suffix = ss.get("suffix") or ''
    s += ")%s" % suffix
    
    return s
