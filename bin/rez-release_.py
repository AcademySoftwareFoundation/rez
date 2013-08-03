#!!REZ_PYTHON_BINARY!

import sys
import os
import optparse
import rez_release as rezr
import sigint

#
# command-line
#
p = optparse.OptionParser(usage="Usage: rez-release [options]")
p.add_option("-m", "--message", dest="message", default=None,
	help="specify commit message, do not prompt user. VCS log will still be appended.")
p.add_option("-n", "--no-message", dest="nomessage", action="store_true", default=False,
	help="commit with no message. VCS log will still be appended [default = %default].")
p.add_option("-j", "--jobs", dest="jobs", type="int", default=1,
	help="specifies the number of jobs (commands) to run simultaneously. [default = %default]")
p.add_option("--allow-not-latest", dest="nolatest", action="store_true", default=False,
	help="allows release of version earlier than the latest release. Do NOT use this option \
unless you have to and you have good reason. [default = %default].")
p.add_option("-t", "--time", dest="time", default="0",
	help="ignore packages newer than the given epoch time [default = current time]")

release_modes = rezr.list_available_release_modes(os.getcwd())
default_mode = release_modes[0]
unavailable_release_modes = [mode for mode in rezr.list_release_modes() if mode not in release_modes]

p.add_option("--mode", dest="mode", default=default_mode,
	help="the release procedure: %s [default = %s] (unavailable: %s)" % \
		(', '.join(release_modes),
		 default_mode,
		 ', '.join(unavailable_release_modes)))

(opts, args) = p.parse_args()


#
# release
#

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
