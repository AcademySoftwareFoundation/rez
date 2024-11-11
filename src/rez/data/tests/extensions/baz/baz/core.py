def get_message_from_baz():
    from rez.config import config
    message = config.plugins.command.baz.message
    return message
