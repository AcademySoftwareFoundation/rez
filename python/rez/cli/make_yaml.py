'''
Create a template 'package.yaml' file
'''

def setup_parser(parser):
    parser.add_argument("path", default=".", nargs="?")

def command(opts):
    from uuid import uuid4
    from getpass import getuser
    from platform import system
    import os

    yamlpath = os.path.join(opts.path, "package.yaml")

    info = {'user': getuser(),
            'platform': os.getenv('REZ_PLATFORM', system()),
            'uuid': str(uuid4())}

    with open(yamlpath, 'w') as f:
        f.write("""config_version : 0

name: enter-package-name

version: 0.0.0

uuid:  %(uuid)s

authors:
- %(user)s

description: >
 Enter description here. Multiline is ok, but make sure
 that you leave the single leading space on each line.

variants:
- [ %(platform)s ]

requires:
- required-package-1
- required-package-N

commands:
- export some-sensible-bashism-eg-$PATH=$PATH:!ROOT!/bin
""" % info)
