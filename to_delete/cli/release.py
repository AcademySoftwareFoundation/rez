'''
Build and release a rez package.
'''
import sys
import os
import rez.release as rezr
import rez.sigint

#
# command-line
#
def setup_parser(parser):
#     p = optparse.OptionParser(usage="Usage: rez-release [options]")
    parser.add_argument("-m", "--message", dest="message", default=None,
                        help="specify commit message, do not prompt user. VCS log will still be appended.")
    parser.add_argument("-n", "--no-message", dest="nomessage", action="store_true", default=False,
                        help="commit with no message. VCS log will still be appended.")
    parser.add_argument("-j", "--jobs", dest="jobs", type=int, default=1,
                        help="specifies the number of jobs (commands) to run simultaneously.")
    parser.add_argument("--allow-not-latest", dest="nolatest", action="store_true", default=False,
                        help="allows release of version earlier than the latest release. Do NOT use this option \
    unless you have to and you have good reason..")
    parser.add_argument("-t", "--time", dest="time", default="0",
                        help="ignore packages newer than the given epoch time [default = current time]")

    release_modes = rezr.list_available_release_modes(os.getcwd())
    default_mode = release_modes[0]
    unavailable_release_modes = [mode for mode in rezr.list_release_modes() if mode not in release_modes]

    parser.add_argument("--mode", dest="mode", default=default_mode,
                        help="the release procedure: %s [default = %s] (unavailable: %s)" %
                       (', '.join(release_modes),
                        default_mode,
                        ', '.join(unavailable_release_modes)))

# (opts, args) = p.parse_args()


def command(opts, parser=None):
    msg = opts.message
    if (not msg) and (opts.nomessage):
        msg = ""

    rezr.release_from_path(".", msg, opts.jobs, opts.time, opts.nolatest, opts.mode)

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
