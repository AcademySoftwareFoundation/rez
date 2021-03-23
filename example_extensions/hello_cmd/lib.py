
def get_message_from_world():
    from rez.config import config
    message = config.plugins.command.world.message
    return message
