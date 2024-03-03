# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import json
from json import dumps  # noqa (forwarded)


def loads(data):
    return json.loads(data)
