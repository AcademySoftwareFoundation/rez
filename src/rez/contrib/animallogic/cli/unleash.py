import os
import re
import subprocess
import sys
import urllib2

from rez.packages import Package
from rez.release_vcs import create_release_vcs
from rez.build_system import create_build_system
from rez.build_process import LocalSequentialBuildProcess
from rez.cli.build import parse_build_args
from rez.cli.build import add_extra_build_args
from rez.cli.build import add_build_system_args

ROOT_PATH = os.path.dirname(os.path.dirname(__file__))
REZ_RELEASE_PACKAGES_PATH = os.getenv("REZ_RELEASE_PACKAGES_PATH")
LAUNCHER_COMMAND = "/film/tools/launcher2CL/current/generic/launch-linux.sh"
LAUNCHER_PRESET = "/toolsets/Department/RnD/Unleash"
UNLEASHER_COMMAND = os.path.join(ROOT_PATH, "bin", "_unleasher")
UNLEASH_FLAVOUR = "package"
UNLEASH_TARGET = "film_tools_packages"
USERNAME = os.getenv("USER")
ARK_URL = os.environ.get("ARK_URL", "http://ark.al.com.au")
LOCATION = "."

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
    parser.add_argument("-e", "--test", dest="test", default=False, action="store_true",
                        help="Run Unleash in test mode.")
    parser.add_argument("--allow-unmanaged-package", dest="allow_unmanaged", default=False, action="store_true",
                        help="Deprecated: Allow the package.yaml file to be unmanaged (not part of an SCM repository).")
    parser.add_argument("--allow-already-tagged", dest="allow_already_tagged", default=False, action="store_true",
                        help="Deprecated: Bypass tag related operations in rez-release.")
    parser.add_argument("-c", "--no-clean", dest="clean", default=True, action="store_false",
                        help="Deprecated: Do not perform a clean build by exporting from SCM.")

    add_extra_build_args(parser)
    add_build_system_args(parser)


def command(opts, parser):

    if opts.allow_unmanaged:
        print "Warning: the --allow-unmanaged-package flag has no effect."

    if opts.allow_already_tagged:
        print "Warning: the --allow-already-tagged flag has no effect."

    if not opts.clean:
        print "Warning: the -c/--no-clean/ flag has no effect."

    if not opts.username:
        raise RezUnleashError("Unable to determine the current user using the USER environment variable.")

    build_args, child_build_args = parse_build_args(opts.BUILD_ARG, parser)
    buildsys_type = opts.buildsys if ("buildsys" in opts) else None

    unleash(opts.message, username=opts.username, unleash_flavour=opts.unleash_flavour,
            unleash_target=opts.unleash_target, test=opts.test,
            launcher_preset=opts.launcher_preset, build_args=build_args,
            child_build_args=child_build_args, buildsys_type=buildsys_type,
            allow_not_latest=opts.allow_not_latest, 
            ignore_auto_messages=opts.ignore_auto_messages, opts=opts)


def unleash(message, username=USERNAME, test=False, unleash_flavour=UNLEASH_FLAVOUR,
            unleash_target=UNLEASH_TARGET, launcher_preset=LAUNCHER_PRESET, buildsys_type=None,     
            build_args=None, child_build_args=None, allow_not_latest=False, 
            ignore_auto_messages=False, opts=None):

    working_dir = os.getcwd()

    package = Package(working_dir)
    vcs = create_release_vcs(working_dir)

    name = package.name
    version = package.version
    description = package.metadata["description"]
    message = get_release_message(message)

    if not check_permission(name, username):
        raise RezUnleashError("The user %s does not have permission to release the tool %s." % (name, username))

    if build_args is None:
        build_args = []

    if child_build_args is None:
        child_build_args = []

    buildsys = create_build_system(working_dir,
                                   buildsys_type=buildsys_type,
                                   opts=opts,
                                   verbose=True,
                                   build_args=build_args,
                                   child_build_args=child_build_args)

    builder = LocalSequentialBuildProcess(working_dir,
                                          buildsys,
                                          vcs=vcs,
                                          ensure_latest=(not allow_not_latest),
                                          release_message=message)

    if not ignore_auto_messages:
        message = "%s\n%s" % (message, get_release_message_from_log(vcs, builder))
        builder.release_message = message

    if not builder.release():
        print "Error: the release did not complete successfully."
        sys.exit(1)

    install_path = package.settings.release_packages_path
    base = builder._get_base_install_path(install_path)

    unleash_command = "python %s -p %s -v %s -b %s -f %s -t %s -m \\'%s\\' -d \\'%s\\' %s" % \
                      (UNLEASHER_COMMAND, name, version, base, unleash_flavour, 
                      unleash_target, encode(message), encode(description), "-e" if test else "")

    launch_command = [LAUNCHER_COMMAND, 
                        "-l", "shell", "-r",
                        "-p", launcher_preset,
                        "-c", "\"" + unleash_command + "\""]

    print "--------------------------------------------------------------------------------"
    print "Unleashing..."
    print "--------------------------------------------------------------------------------\n"

    print "Executing: ", launch_command
    
    process = subprocess.Popen(launch_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return_code = process.wait()

    if return_code:
        print "Error: there was a problem unleashing your package."
        print "".join(process.stdout.readlines())

        print "Warning: a tag for this release may still exist on the repository."

    else:
        print "\nPackage %s was unleashed successfully." % package.qualified_name

    sys.exit(return_code)


def get_release_message_from_log(vcs, builder):
    """
    Extract release messages hidden in commit logs. 
    
    These messages are enclosed in <release></release> tags and are entered by
    the developer at commit, not release, time.  They are then extracted here 
    for consolidation with other release messages.
    
    If extractMessageFromLog is True, message comments will be extracted from the 
    Git log.
    """

    install_path = builder.package.settings.release_packages_path
    last_pkg, last_release_info = builder._get_last_release(install_path)

    last_rev = (last_release_info or {}).get("revision")
    return "\n".join(vcs.get_releaselog(previous_revision=last_rev))


def get_message_from_user(prompt="Please enter a release comment terminated with a single '.' line:\n"):
    """
    Prompt the user for a release message that is used with rez-release and 
    Unleash.
    """
    
    def prompt_user_for_input(prompt):
        user_input = []
        
        while True:
            input = raw_input(prompt).strip()
            
            if input == ".":
                break
            elif input != "" or user_input:
                user_input.append(input)
            
            prompt = ""
        
        if not user_input:
            user_input = prompt_user_for_input("You have not entered a valid release comment, please try again:\n")
        
        return user_input
    
    return "\n".join(prompt_user_for_input(prompt))


def get_release_message(message):
    """
    Return the fully composed release message based on the provided options.
    
    If message is a string that points to a readable file, the contents of the
    file are used for the message.  Otherwise message is used as-is.
    
    In Rez 2.0, we should use the VCS plugins to abstract this from
    using Git directly. 
    """

    if message is None:
        return get_message_from_user()

    elif os.path.isfile(message):
        with open(message) as fd:
            return "".join(fd.readlines())

    return message


def encode(input):
    """
    Encode a string such that it is safe to pass through launcher2CL etc, 
    preserving single quotes and newlines.
    """

    return input.replace("\n", "\\\\n").replace("'", "\\\'\"\\\'\"\\\'")


def check_permission(tool, username):
    """
    Check the current user has permission to release this tool in Unleash.
    """

    url = "%s/xml/rest/lpathExpansion?project=kragle&lpath=STAFF(UNLEASHACL[%s],~%s)" % (ARK_URL, tool.lower(), username)

    request = urllib2.Request(url)
    response = urllib2.urlopen(request)
    lines = response.readlines()

    if response.code != 200 or not lines:
        return False

    return "<expansion>/STAFF(%s)</expansion>" % username in lines[0]

