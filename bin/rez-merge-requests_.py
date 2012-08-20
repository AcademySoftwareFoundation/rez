#!!REZ_PYTHON_BINARY!

import sys
import rez_parse_request as rpr


req_str = str(' ').join(sys.argv[1:])
base_pkgs, subshells = rpr.parse_request(req_str)

s = rpr.encode_request(base_pkgs, subshells)
print s
