# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


# Format string used to determine the VCS tag name when releasing. This
# will be formatted using the package being released - any package
# attribute can be referenced in this string, eg "{name}".
#
# It is not recommended to write only '{version}' to the tag. This will
# cause problems if you ever store multiple packages within a single
# repository - versions will clash and this will cause several problems.
tag_name = "{qualified_name}"

# A list of branches that a user is allowed to rez-release from. This
# can be used to block releases from development or feature branches,
# and support a workflow such as "gitflow".  Each branch name should be
# a regular expression that can be used with re.match(), for example
# "^main$".
releasable_branches = []

# If True, a release will be cancelled if the repository has already been
# tagged at the current package's version. Generally this is not needed,
# because Rez won't re-release over the top of an already-released
# package anyway (or more specifically, an already-released variant).
#
# However, it is useful to set this to True when packages are being
# released in a multi-site scenario. Site A may have released package
# foo-1.4, and for whatever reason this package hasn't been released at
# site B. Site B may then make some changes to the foo project, and then
# attempt to release a foo-1.4 that is now different to site A's foo-1.4.
# By setting this check to True, this situation can be avoided (assuming
# that both sites are sharing the same code repository).
#
# Bear in mind that even in the above scenario, there are still cases
# where you may NOT want to check the tag. For example, an automated
# service may be running that detects when a package is released at
# site A, which then checks out the code at site B, and performs a
# release there. In this case we know that the package is already released
# at A, but that's ok because the package hasn't changed and we just want
# to release it at B also. For this reason, you can set tag checking to
# False both in the API and via an option on the rez-release tool.
check_tag = False

git = {
    # If false, cancel a package release if there is no upstream branch.
    "allow_no_upstream": False
}
