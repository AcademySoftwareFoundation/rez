'''
Control the rex interpreter daemon
'''

import pickle
import sys
import rez.rex
import SocketServer
from rez.daemonize import Daemon

BLOCK_SIZE = 512

class TCPHandler(SocketServer.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        data = self.request.recv(BLOCK_SIZE).strip()
#         print "{} wrote:".format(self.client_address[0])
#         print data
        try:
            with open(data) as f:
                result = pickle.load(f)
        except IOError as err:
            print>>sys.stderr, "Failed reading file: {}: {}".format(data, err)
        else:
            script = rez.rex.RexExecutor('bash', result).execute_packages()
            self.request.sendall(script)

class TCPServerDaemon(Daemon):
    def __init__(self, pidfile, port):
        self.port = port
        Daemon.__init__(self, pidfile)

    def run(self):
        server = SocketServer.TCPServer(('localhost', self.port), TCPHandler)
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        server.serve_forever()

def setup_parser(parser):
    parser.add_argument("action", metavar='ACTION',
                        choices=['start', 'stop', 'restart'],
                        help="action to perform on the daemon process")
    parser.add_argument("--port", metavar='PORT', type=int, default=51000,
                        help="server port")

def command(opts):
    daemon = TCPServerDaemon('/tmp/rez-daemon.pid', opts.port)
    if opts.action == 'start':
        daemon.start()
    elif opts.action == 'stop':
        daemon.stop()
    elif opts.action == 'restart':
        daemon.restart()
