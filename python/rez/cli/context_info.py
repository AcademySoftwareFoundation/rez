'''
Report on the current rez-configured environment.
'''
import os
import sys

def setup_parser(parser):
    pass

def command(opts):
    import time

    print
    print "running rez-config v" + os.getenv('REZ_VERSION')
    print

    context_file = os.getenv("REZ_CONTEXT_FILE")
    if not context_file or not os.path.exists(context_file):
        print "not in a resolved environment context."
        sys.exit(1)

    resolve_mode = os.getenv('REZ_RESOLVE_MODE')
    request_time = int(os.getenv('REZ_REQUEST_TIME'))
    readable_time = time.strftime("%a %b %d %H:%M:%S %Z %Y",
                                  time.localtime(request_time))
    print "requested packages (mode=%s, time=%s: %s):" % (resolve_mode,
                                                          request_time,
                                                          readable_time)

    request = os.getenv('REZ_REQUEST').split(' ')
    print '\n'.join(request)
    print
    raw_request = os.getenv('REZ_RAW_REQUEST')
    if raw_request:
        raw_request = raw_request.split(' ')
        reqmatch = [x for x in request if x in raw_request]
        if not reqmatch:
            print "raw request:"
            print ' '.join(raw_request)
            print

    resolve = sorted(os.getenv('REZ_RESOLVE').split(' '))
    column = max([len(pkg) for pkg in resolve])
    column += 8
    local_path = os.getenv('REZ_LOCAL_PACKAGES_PATH')
    print 'resolved packages:'
    for pkg in resolve:
        name = pkg.split('-')[0]
        root = os.environ['REZ_%s_ROOT' % name.upper()]
        local = (' (local)' if root.startswith(local_path) else '')
        line = pkg.ljust(column) + root + local
        print line

    print
    print "number of failed attempts: " + os.getenv('REZ_FAILED_ATTEMPTS')

    print
    print "context file:"
    print context_file

    print

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
