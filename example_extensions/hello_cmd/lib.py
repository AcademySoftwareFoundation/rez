# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


def get_message_from_world():
    from rez.config import config
    message = config.plugins.command.world.message
    return message
