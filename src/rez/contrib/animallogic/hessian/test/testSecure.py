# -*- coding: UTF-8 -*-
#
# Hessian protocol implementation test
# This file contains HTTPS tests. It is separated into own file as 
# it has additional depencies (see also secureServer.py)
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
from time import sleep
from threading import Thread

from rez.contrib.animallogic.hessian.secureServer import *
from rez.contrib.animallogic.hessian.client import HessianProxy


__revision__ = "$Rev: 11811 $"


TEST_PORT = 7771


class _TestHandler(HessianHTTPSRequestHandler):
    
    def echo(self, some):
        return some
    
    message_map = { "echo" : echo }


class _TestSecureServer(Thread):

    def run(self):
        self.online = False
        print "\nStarting test HTTPS server"
        server_address = ('', TEST_PORT)
        httpd = SecureHTTPServer(server_address, _TestHandler)
        print "HTTPS server is serving from ", server_address
        self.online = True
        httpd.serve_forever()


def _testHttps():
    srv = _TestSecureServer()
    srv.setDaemon(True)
    srv.start()
    
    sleep(1) # wait until server starts
    while not srv.online:
        sleep(1)
    
    proxy = HessianProxy("https://localhost:" + `TEST_PORT`)
    assert proxy.echo("hello") == "hello"


if __name__ == "__main__":
    print "Testing additional transports"
    _testHttps()
    print "\nTests passed."
    
