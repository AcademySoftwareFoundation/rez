"""
Functions for parsing rez parenthesised syntax, used to create subshells on the fly (see the comments
in bin/rez-env-autowrappers_.py)
"""
request_parser = None

class RequestParser(object):
    def __init__(self):
        import pyparsing as pp
        _pkg = pp.Regex("[a-zA-Z_0-9~<=^\\.\\-\\!\\+]+").setParseAction(self._parse_pkg)

        _subshell_label = pp.Regex("[a-zA-Z0-9_]+")
        _subshell_label_decl = (_subshell_label + ':').setParseAction(self._parse_subshell_label)
        _subshell_body = (_subshell_label_decl * (0, 1)) + pp.OneOrMore(_pkg)
        _subshell_prefix = (pp.Regex("[a-zA-Z0-9_]+\\(") ^ '(').setParseAction(self._parse_subshell_prefix)
        _subshell_suffix = (pp.Regex("\\)[a-zA-Z0-9_]+") ^ ')').setParseAction(self._parse_subshell_suffix)
        _subshell = _subshell_prefix + _subshell_body + _subshell_suffix

        _request = pp.OneOrMore(_pkg ^ _subshell).setParseAction(self._parse_subshell_request)
        self.expr = _request + pp.ZeroOrMore('|' + _request)

    def _reset(self):
        self.base_pkgs = []
        self.subshells = {}
        self.merged_base_pkgs = []
        self.merged_subshells = {}
        self.curr_subshell = None

    def _parse_pkg(self, s, loc, toks):
        pkg_str = str('').join(toks)
        if self.curr_subshell is None:
            self.base_pkgs.append(pkg_str)
        else:
            self.curr_subshell["pkgs"].append(pkg_str)

    def _parse_subshell_label(self, s, loc, toks):
        self.curr_subshell["label"] = toks[0]

    def _parse_subshell_prefix(self, s, loc, toks):
        self.curr_subshell = {
            "pkgs": [],
            "prefix": '',
            "suffix": ''
        }
        prefix_str = toks[0][:-1]
        if prefix_str:
            self.curr_subshell["prefix"] = prefix_str

    def _parse_subshell_suffix(self, s, loc, toks):
        suffix_str = toks[0][1:]
        if suffix_str:
            self.curr_subshell["suffix"] = suffix_str
        if "label" not in self.curr_subshell:
            pkg_fam = self.curr_subshell["pkgs"][0].split('-')[0]
            label_str = self.curr_subshell["prefix"] + pkg_fam + self.curr_subshell["suffix"]
            self.curr_subshell["label"] = label_str

        subshell_name = self.curr_subshell["label"]
        if subshell_name in self.subshells:
            # FIXME: raise error instead of calling sys.exit
            print >> sys.stderr, "Error: subshell '%s' is defined more than once!" % subshell_name
            sys.exit(1)

        self.subshells[subshell_name] = self.curr_subshell
        self.curr_subshell = None

    def _parse_subshell_request(self, s, loc, toks):
        self.merged_base_pkgs = merge_pkgs(self.merged_base_pkgs,
                                           self.base_pkgs)
        self.merged_subshells = _merge_subshells(self.merged_subshells,
                                                 self.subshells)
        self.base_pkgs = []
        self.subshells = {}

    def parseString(self, request):
        self._reset()
        self.expr.parseString(request, parseAll=True)
        return (self.merged_base_pkgs, self.merged_subshells)

def parse_request(request):
    """
    Parses any request string, including parenthesised form, and merging (pipe operator).
    @return (base_pkgs, subshells). base_pkgs is a list of packages in the 'master' shell, ie
        outside of any parenthesised subshell. 'subshells' is a dict of subshells, keyed on the
        subshell name.
    """
    global request_parser
    if request_parser is None:
        request_parser = RequestParser()
    return request_parser.parseString(request)


def merge_pkgs(pkgs, override_pkgs):

    def _parse_pkg(pkg):
        rm = pkg.startswith('^')
        if rm:
            if len(pkg.split('-')) > 1:
                # FIXME: use a proper rez exception
                raise Exception("Only unversioned package allowed with the remove operator '^'")
            pkg = pkg[1:]
        return (pkg.split('-')[0], rm)

    merged_pkgs = []
    override_pkgs2 = override_pkgs[:]

    opkgs = {}
    for pkg in override_pkgs:
        name, rm = _parse_pkg(pkg)
        opkgs[name] = (pkg, rm)

    for pkg in pkgs:
        name, rm = _parse_pkg(pkg)
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

    for name, ss in subshells.iteritems():
        oss = override_subshells.get(name)
        if oss:
            merged_pkgs = merge_pkgs(ss["pkgs"], oss["pkgs"])
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
