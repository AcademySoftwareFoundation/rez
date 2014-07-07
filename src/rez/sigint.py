import os
import sys
import signal



def signull(signum, frame):
    pass

def sigbase_handler(signum, frame):
    # kill all child procs
    signal.signal(signal.SIGINT, signull)
    signal.signal(signal.SIGTERM, signull)
    os.killpg(os.getpgid(0), signum)
    sys.exit(1)

# exit gracefully on ctrl-C
def sigint_handler(signum, frame):
    print >> sys.stderr, "Interrupted by user"
    sigbase_handler(signum, frame)

# exit gracefully on terminate.
def sigterm_handler(signum, frame):
    print >> sys.stderr, "Terminated"
    sigbase_handler(signum, frame)

signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigterm_handler)



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
