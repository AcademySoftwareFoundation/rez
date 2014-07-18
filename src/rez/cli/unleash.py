'''
Build a package from source and deploy it using the Unleash subsystem.
'''

from rez.cli.build import setup_parser_common
from rez.release_vcs import get_release_vcs_types
from rez.contrib.animallogic.unleash.unleash import LAUNCHER_PRESET
from rez.contrib.animallogic.unleash.unleash import UNLEASH_FLAVOUR
from rez.contrib.animallogic.unleash.unleash import UNLEASH_TARGET
from rez.contrib.animallogic.unleash.unleash import USERNAME
from rez.contrib.animallogic.unleash.unleash import unleash
import os


def setup_parser(parser):

    parser.add_argument("-m", "--message", dest="message", default=None,
                        help="Specify commit message. Automatic release messages will still be appended unless used with the --ignore-auto-messages option.")
    parser.add_argument("--ignore-auto-messages", dest="ignore_auto_messages", action="store_true", default=False, 
                        help="Do not extract release messages from the SCM commit log.")
    parser.add_argument("--allow-not-latest", "--no-latest", dest="allow_not_latest", action="store_true", default=False, 
                        help="Allows release of version earlier than the latest release.")
    parser.add_argument("-u", "--user", dest="username", default=USERNAME,
                        help="Username for the current release - can be used when running through Jenkins.")
    parser.add_argument("-p", "--preset", dest="launcher_preset", default=LAUNCHER_PRESET,
                        help="The name of the launcher preset to run Unleash under.")
    parser.add_argument("-f", "--flavour", dest="unleash_flavour", default=UNLEASH_FLAVOUR,
                        help="The name of the Unleash flavour to use.")
    parser.add_argument("-t", "--target", dest="unleash_target", default=UNLEASH_TARGET,
                        help="The name of the Unleash target to use.")
    parser.add_argument("--vcs", type=str, choices=get_release_vcs_types(),
                        help="force the vcs system to use")
    parser.add_argument("-e", "--test", dest="test", default=False, action="store_true",
                        help="Run Unleash in test mode.")
    parser.add_argument("--allow-unmanaged-package", dest="allow_unmanaged", default=False, action="store_true",
                        help="Deprecated: Allow the package.yaml file to be unmanaged (not part of an SCM repository).")
    parser.add_argument("--allow-already-tagged", dest="allow_already_tagged", default=False, action="store_true",
                        help="Deprecated: Bypass tag related operations in rez-release.")
    parser.add_argument("-c", "--no-clean", dest="clean", default=True, action="store_false",
                        help="Deprecated: Do not perform a clean build by exporting from SCM.")

    setup_parser_common(parser)


def command(opts, parser):

    if opts.allow_unmanaged:
        print "Warning: the --allow-unmanaged-package flag has no effect."

    if opts.allow_already_tagged:
        print "Warning: the --allow-already-tagged flag has no effect."

    if not opts.clean:
        print "Warning: the -c/--no-clean/ flag has no effect."

    if not opts.username:
        raise RezUnleashError("Unable to determine the current user using the USER environment variable.")

    buildsys_type = opts.buildsys if ("buildsys" in opts) else None
    working_dir = os.getcwd()

    unleash(working_dir, opts.message, username=opts.username, unleash_flavour=opts.unleash_flavour,
            unleash_target=opts.unleash_target, test=opts.test,
            launcher_preset=opts.launcher_preset, build_args=opts.build_args,
            child_build_args=opts.child_build_args, buildsys_type=buildsys_type,
            allow_not_latest=opts.allow_not_latest, 
            ignore_auto_messages=opts.ignore_auto_messages, opts=opts)

