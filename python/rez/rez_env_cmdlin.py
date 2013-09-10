#
# Module for dealing just with command-line options for rez-env. This is needed because the
# autowrapper stuff needs to share some of this code. Also it means we get nice optparse behaviour
# in bash.
#

import optparse
import sys

_g_usage = "rez-env [options] pkg1 pkg2 ... pkgN"


class OptionParser2(optparse.OptionParser):
    def exit(self, status=0, msg=None):
        if msg:
            sys.stderr.write(msg)
        sys.exit(1)


def get_cmdlin_parser():
    p = OptionParser2(usage=_g_usage)

    p.add_option("-q", "--quiet", dest="quiet", action="store_true", default=False, \
        help="Suppress unnecessary output [default = %default]")
    p.add_option("-b", "--build", dest="build", action="store_true", default=False, \
        help="Include build-only package requirements [default = %default]")
    p.add_option("-o", "--no_os", dest="no_os", action="store_true", default=False, \
        help="Stop rez-env from implicitly requesting the operating system package [default = %default]")
    p.add_option("--no-cache", dest="no_cache", action="store_true", default=False, \
        help="disable caching [default = %default]")
    p.add_option("-u", "--use_blacklisted", dest="use_blacklisted", action="store_true", default=False, \
        help="Potentially use package versions that have been blacklisted [default = %default]")
    p.add_option("-g", "--use_archived", dest="use_archived", action="store_true", default=False, \
        help="Potentially use package versions that have been archived [default = %default]")
    p.add_option("-d", "--no_assume_dt", dest="no_assume_dt", action="store_true", default=False, \
        help="Do not assume dependency transitivity [default = %default]")
    p.add_option("-m", "--mode", dest="mode", type="string", default="latest", \
        help="Set the package resolution mode [default=%default]")
    p.add_option("-p", "--prompt", dest="prompt", type="string", default=">", \
        help="Set the prompt decorator [default=%default]")
    p.add_option("-i", "--time", dest="time", type="int", default=0, \
        help="Ignore packages newer than the given epoch time")
    p.add_option("-r", "--rcfile", dest="rcfile", type="string", default='', \
        help="Source this file after the new shell is invoked")
    p.add_option("--tmpdir", dest="tmpdir", type="string", default='', \
        help="Set the temp directory manually, /tmp otherwise")    
    p.add_option("--propogate-rcfile", dest="prop_rcfile", action="store_true", default=False, \
        help="Propogate rcfile into subshells")
    p.add_option("-s", "--stdin", dest="stdin", action="store_true", default=False, \
        help="Read commands from stdin, rather than starting an interactive shell [default = %default]")
    p.add_option("-a", "--add_loose", dest="add_loose", action="store_true", default=False, \
        help="Add mode (loose). Packages will override or add to the existing request list [default = %default]")
    p.add_option("-t", "--add_strict", dest="add_strict", action="store_true", default=False, \
        help="Add mode (strict). Packages will override or add to the existing resolve list [default = %default]")
    p.add_option("-f", "--view_fail", dest="view_fail", type=int, default=-1, \
        help="View the dotgraph for the Nth failed config attempt")
    p.add_option("--no-local", dest="no_local", action="store_true", default=False, \
        help="don't load local packages")

    return p


# rez-env uses this, nothing else
if __name__ == "__main__":

    p = get_cmdlin_parser()
    (opts, args) = p.parse_args()
    print str(' ').join(args)

    d = eval(str(opts))
    for k,v in d.iteritems():
        ku = k.upper()
        print "_REZ_ENV_OPT_%s='%s'" % (ku, str(v))



#    Copyright 2008-2012 Dr D Studios Pty Limited (ACN 127 184 954) (Dr. D Studios)
#
#    This file is part of Rez.
#
#    Rez is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Rez is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Rez.  If not, see <http://www.gnu.org/licenses/>.
