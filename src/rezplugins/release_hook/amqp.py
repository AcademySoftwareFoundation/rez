# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Publishes a message to the broker.
"""
from __future__ import print_function

from rez.release_hook import ReleaseHook
from rez.utils.logging_ import print_error, print_debug
from rez.utils.amqp import publish_message
from rez.vendor.six import six
from rez.config import config


basestring = six.string_types[0]


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
