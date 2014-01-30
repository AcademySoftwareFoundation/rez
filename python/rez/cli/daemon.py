'''
Control the rex interpreter daemon
'''

import pickle
import sys
import rez.rex
import SocketServer
import select
import pprint
import rez
from rez.daemonize import Daemon

BLOCK_SIZE = 2048
PORT = 51000

def env_string_to_dict(env):
    environ = {}
    for line in env.split('\n'):
        # the body of a bash function is prefixed with a space
        if line.startswith(' '):
            continue
        try:
            key, value = line.split('=', 1)
        except ValueError:
            # not an env pair
            pass
        else:
            # the definition of a bash function starts with a space
            if value.startswith('()'):
                continue
            environ[key] = value
    return environ

class TCPHandler(SocketServer.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
#         print "{} wrote:".format(self.client_address[0])
        # self.request is the TCP socket connected to the client
        envstr = ''
        while 1:
            data = self.request.recv(BLOCK_SIZE)
            if not data:
                print "EMPTY"
                break
            envstr += data
            if envstr.endswith('\n\n'):
                print "DONE"
                break
        environ = env_string_to_dict(envstr[:-1])
#         pprint.pprint(environ)

        if environ['REZ_VERSION'] != rez.__version__:
            self.server._shutdown_request = True
            self.request.sendall("STALE")
            return

        filepath = environ['REZ_CONTEXT']
        try:
            with open(filepath) as f:
                result = pickle.load(f)
        except IOError as err:
            print>>sys.stderr, "Failed reading file: {}: {}".format(filepath, err)
        else:
            script = rez.rex.RexExecutor('bash', result).execute_packages()
            self.request.sendall(script)

class SimpleTCPServer(SocketServer.TCPServer):
    def __init__(self, server_address, RequestHandlerClass):
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
        self._shutdown_request = False

    def serve_forever(self, poll_interval=0.5):
        """provide an override that can be shutdown from a request handler.
        The threading code in the BaseSocketServer class prevented this from working
        even for a non-threaded blocking server.
        """
        try:
            while not self._shutdown_request:
                # XXX: Consider using another file descriptor or
                # connecting to the socket to wake this up instead of
                # polling. Polling reduces our responsiveness to a
                # shutdown request and wastes cpu at all other times.
                r, w, e = SocketServer._eintr_retry(select.select, [self], [], [],
                                       poll_interval)
                if self in r:
                    self._handle_request_noblock()
        finally:
            self._shutdown_request = False

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    def __init__(self, server_address, RequestHandlerClass):
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)

class ServerDaemon(Daemon):
    def __init__(self, pidfile, port):
        self.port = port
        Daemon.__init__(self, pidfile)

    def serve(self):
#         server = SocketServer.UDPServer(('localhost', self.port), UDPHandler)
        server = SimpleTCPServer(('localhost', self.port), TCPHandler)
#         server = ThreadedTCPServer(('localhost', self.port), TCPHandler)
        server.allow_reuse_address = True
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        server.serve_forever()

    def run(self):
        self.serve()
        self.stop()


class UDPHandler(SocketServer.BaseRequestHandler):
    """
    This class works similar to the TCP handler class, except that
    self.request consists of a pair of data and client socket, and since
    there is no connection the client address must be given explicitly
    when sending data back via sendto().
    """

    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        print "{} wrote:".format(self.client_address[0])
        if data:
            pprint.pprint(env_string_to_dict(data))
        else:
            print "no data"
#         socket.sendto(data.upper(), self.client_address)

def setup_parser(parser):
    parser.add_argument("action", metavar='ACTION',
                        choices=['start', 'stop', 'restart', 'serve'],
                        help="action to perform on the daemon process")
    parser.add_argument("--port", metavar='PORT', type=int, default=PORT,
                        help="server port")

def command(opts):
    import getpass
    daemon = ServerDaemon('/tmp/rez-daemon-%s.pid' % getpass.getuser(),
                             opts.port)
    if opts.action == 'start':
        daemon.start()
    elif opts.action == 'stop':
        daemon.stop()
    elif opts.action == 'restart':
        daemon.restart()
    elif opts.action == 'serve':  # a normal blocking server
        daemon.serve()
