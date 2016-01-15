"""
Publishes a message to the broker.

The message is a json encoded dictionary of the form -
    {
        package : {
            handle : {}
        },
        variants : [
            { handle : {} },
            { handle : {} }
        ]
    }

"""
from rez.release_hook import ReleaseHook
from rez.utils.logging_ import print_warning, print_debug
from rez.vendor.amqp import Connection, basic_message
import json
import socket


class AmqpReleaseHook(ReleaseHook):

    schema_dict = {
        "host":                     basestring,
        "port":                     int,
        "userid":                   basestring,
        "password":                 basestring,
        "connect_timeout":          int,
        "exchange_name":            basestring,
        "exchange_type":            basestring,
        "exchange_durable":         bool,
        "exchange_auto_delete":     bool,
        "exchange_routing_key":     basestring,
        "message_delivery_mode":    int}

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
        data = dict()
        data["package"] = dict(handle=package.handle.to_dict())

        data["variants"] = []
        for variant in variants:
            variants_data = dict(handle=variant.handle.to_dict())
            data["variants"].append(variants_data)

        self.publish_message(data)

    def publish_message(self, data):
        if not self.settings.host:
            print_warning("Did not publish message, host is not specified")
            return

        try:
            conn = Connection(host=self.settings.host,
                              port=self.settings.port,
                              userid=self.settings.userid,
                              password=self.settings.password,
                              connect_timeout=self.settings.connect_timeout)
        except socket.error as e:
            print_warning("Cannot connect to the message broker: %s" % (e))
            return

        channel = conn.channel()

        # Declare the exchange
        try:
            channel.exchange_declare(self.settings.exchange_name, self.settings.exchange_type,
                                     durable=self.settings.exchange_durable,
                                     auto_delete=self.settings.exchange_auto_delete)
        except Exception as e:
            print_warning("Failed to declare an exchange: %s" % (e))
            return

        # build the message
        msg = basic_message.Message(body=json.dumps(data),
                                    delivery_mode=self.settings.message_delivery_mode)

        # publish the message
        try:
            channel.basic_publish(msg, self.settings.exchange_name,
                                  self.settings.exchange_routing_key)
            print_debug("Published message: %s" % (data))
        except Exception as e:
            print_warning("Failed to publish message: %s" % (e))
            return


def register_plugin():
    return AmqpReleaseHook
