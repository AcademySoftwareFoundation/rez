from rez.config import config
from rez.packages import load_developer_package
from rez.release_vcs import create_release_vcs
from rez.build_system import create_build_system
from rez.build_process import LocalSequentialBuildProcess
from rez.contrib.animallogic.unleash.exceptions import UnleashError
from rez.util import print_warning
import os
import subprocess
import sys
import urllib2


ARK_URL = config.ark_url
LAUNCHER_PRESET = config.unleash_launcher_preset
LAUNCHER_COMMAND = "/film/tools/launcher2CL/current/generic/launch-linux.sh"
UNLEASH_FLAVOUR = config.unleash_flavour
UNLEASH_TARGET = config.unleash_target
ROOT_PATH = os.path.dirname(__file__)
UNLEASHER_COMMAND = os.path.join(ROOT_PATH, "bin", "_unleasher")
USERNAME = os.getenv("USER")


def unleash(working_dir, message, username=USERNAME, test=False, unleash_flavour=UNLEASH_FLAVOUR,
            unleash_target=UNLEASH_TARGET, launcher_preset=LAUNCHER_PRESET, buildsys_type=None,     
            build_args=None, child_build_args=None, allow_not_latest=False, 
            ignore_auto_messages=False, opts=None):

    package = load_developer_package(working_dir)
    vcs = create_release_vcs(working_dir)

    name = package.name
    version = package.version
    description = package.description
    message = get_release_message(message)

    if not check_permission(name, username):
        raise UnleashError("The user %s does not have permission to release the tool %s." % (username, name))

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

    config.override('release_packages_path', package.config.unleash_packages_path)

    builder.release()

    install_path = package.config.unleash_packages_path
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


def check_permission(tool, username):
    """
    Check the current user has permission to release this tool in Unleash.
    """

    url = "%s/xml/rest/lpathExpansion?project=global&lpath=STAFF(UNLEASHACL[%s],~%s)" % (ARK_URL, tool.lower(), username)

    request = urllib2.Request(url)
    response = urllib2.urlopen(request)
    lines = response.readlines()

    if response.code != 200 or not lines:
        return False

    return "<expansion>/STAFF(%s)</expansion>" % username in lines[0]


def get_release_message_from_log(vcs, builder):
    """
    Extract release messages hidden in commit logs. 
    
    These messages are enclosed in <release></release> tags and are entered by
    the developer at commit, not release, time.  They are then extracted here 
    for consolidation with other release messages.
    
    If extractMessageFromLog is True, message comments will be extracted from the 
    Git log.
    """

    install_path = builder.package.config.release_packages_path

    last_package = builder._get_last_release(install_path)

    if not last_package:
        print_warning("Unable to find last package for release comments.")
        return ""

    last_revision = last_package.revision
    return "\n".join(vcs.get_release_log(previous_revision=last_revision))


def encode(input):
    """
    Encode a string such that it is safe to pass through launcher2CL etc, 
    preserving single quotes and newlines.
    """

    return input.replace("\n", "\\\\n").replace("'", "\\\'\"\\\'\"\\\'")

