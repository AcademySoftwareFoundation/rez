# -*- coding: UTF-8 -*-
#
# Hessian protocol implementation
# This file contains simple RPC over HTTPS server code.
#
# Protocol specification can be found here:
# http://www.caucho.com/resin-3.0/protocols/hessian-1.0-spec.xtp
#
# HTTPS pieces of code are based on receipe "Simple HTTP server supporting 
# SSL secure communications" by Sébastien Martini published at ActiveState 
# Programmer Network.
#
# This code requires pyOpenSSL (and OpenSSL itself).
#
# Copyright 2006 Petr Gladkikh (batyi at sourceforge net)
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
from server import HessianHTTPRequestHandler

import socket, os
from SocketServer import BaseServer
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
try:
    from OpenSSL import SSL
except:
    print 'cant load OpenSSL library'

__revision__ = "$Rev: 11811 $"

class HessianHTTPSRequestHandler(HessianHTTPRequestHandler):
    def setup(self):
        self.connection = self.request
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)


class SecureHTTPServer(HTTPServer):
    def __init__(self, server_address, HandlerClass, keyfile = 'hessian/test/server.pem'):
        BaseServer.__init__(self, server_address, HandlerClass)
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_privatekey_file (keyfile)
        ctx.use_certificate_file(keyfile)
        self.socket = SSL.Connection(ctx, socket.socket(self.address_family, 
                                                        self.socket_type))
        self.server_bind()
        self.server_activate()
