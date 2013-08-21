'''
placeholder
'''

def setup_parser(parser):
    parser.add_argument("request", nargs='+')

def command(opts):
    import rez.rez_parse_request as rpr
    
    req_str = str(' ').join(opts.request)
    base_pkgs, subshells = rpr.parse_request(req_str)
    
    s = rpr.encode_request(base_pkgs, subshells)
    print s
