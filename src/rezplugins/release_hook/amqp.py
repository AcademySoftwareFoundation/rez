"""
Publishes a message to the broker.
"""
from __future__ import print_function
from rez.release_hook import ReleaseHook
from rez.utils.logging_ import print_error, print_debug
from rez.utils.amqp import publish_message
from rez.config import config

try:
    basestring
except NameError:
    # Python 3+
    basestring = str


class AmqpReleaseHook(ReleaseHook):
    """
    Publishes a message to the broker.

    The message is a json encoded dictionary of the form -
        {
            package : {
                handle : {},
                name : ...
                version : ...
                user: ... (who released the package)
                qualified_name : ...
                uri : ...
            },
            variants : [
                { handle : {} },
                { handle : {} }
            ]
        }
    """
    schema_dict = {
        "host":                     basestring,
        "userid":                   basestring,
        "password":                 basestring,
        "connect_timeout":          int,
        "exchange_name":            basestring,
        "exchange_routing_key":     basestring,
        "message_delivery_mode":    int,
        "message_attributes":       dict}

    @classmethod
    def name(cls):
        return "amqp"

    def __init__(self, source_path):
        super(AmqpReleaseHook, self).__init__(source_path)

    def post_release(self, user, install_path, variants, **kwargs):
        if variants:
            package = variants[0].parent
        else:
            package = self.package

        # build the message dict
        data = {}
        data["package"] = dict(
            name=package.name,
            version=str(package.version),
            qualified_name=package.qualified_name,
            uri=package.uri,
            handle=package.handle.to_dict())

        # FIXME Do this until user added as package attribute
        from getpass import getuser
        data["package"]["user"] = getuser()

        data["variants"] = []
        for variant in variants:
            variants_data = dict(handle=variant.handle.to_dict())
            data["variants"].append(variants_data)

        # add message attributes
        data.update(self.settings.message_attributes)

        self.publish_message(data)

    def publish_message(self, data):
        if not self.settings.host:
            print_error("Did not publish message, host is not specified")
            return

        routing_key = self.settings.exchange_routing_key
        print("Publishing AMQP message on %s..." % routing_key)

        publish_message(
            host=self.settings.host,
            amqp_settings=self.settings,
            routing_key=routing_key,
            data=data
        )

        if config.debug("package_release"):
            print_debug("Published message: %s" % (data))


def register_plugin():
    return AmqpReleaseHook


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
