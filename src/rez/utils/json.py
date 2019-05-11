from __future__ import absolute_import
import json
from json import dumps  # noqa (forwarded)
import sys


if sys.version_info.major >= 3:

    def loads(data):
        return json.loads(data)

# py2
else:

    def loads(json_text):
        """Avoids returning unicodes in py2.

        https://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-from-json
        """
        def _byteify(input, ignore_dicts=False):
            if isinstance(input, list):
                return [_byteify(x) for x in input]
            elif isinstance(input, unicode):
                try:
                    return str(input)
                except UnicodeEncodeError:
                    return input
            elif isinstance(input, dict) and not ignore_dicts:
                return {
                    _byteify(k, ignore_dicts=True): _byteify(v, True)
                    for k, v in input.items()
                }
            else:
                return input

        return _byteify(json.loads(json_text, object_hook=_byteify))
