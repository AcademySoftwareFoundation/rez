<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright Contributors to the Rez Project -->

# Security Policy

## Reporting a Vulnerability

If you think you've found a potential vulnerability in rez, please
report it by filing a GitHub [security
advisory](https://github.com/AcademySoftwareFoundation/rez/security/advisories/new). Alternatively,
email security@rez-project.io and provide your contact info for further
private/secure discussion. If your email does not receive a prompt
acknowledgement, your address may be blocked. If you request anonymity,
your name and contact information will not be published. Otherwise,
credit will be given in notices related to the vulnerability.

Our policy is to acknowledge the receipt of vulnerability reports
within 48 hours. Our policy is to address critical security vulnerabilities
rapidly and post patches within 14 days if possible.

## Known Vulnerabilities

The only currently known security vulnerability is issue [#417](https://github.com/AcademySoftwareFoundation/rez/issues/417), reported by @ttanimura.
No others are known at this time.

See the [release notes](CHANGES.md) for more information.

## Supported Versions

In general, the rez project release strategy is purely sequential, and we will drop support for any
major version which is not the current development major version. However, we may at our discretion issue
patches for prior major versions with compelling reasoning. The rez project team takes compatibility very
seriously, deprecations are telegraphed, and forward compatibility is incredibly important, making it
reasonable to expect that users of rez attempt to stay close to the newest version as possible.

## Signed Releases

Signed releases are not yet supported.

We plan to add signed releases soon. The following details are speculative but likely:

Release artifacts are signed via
[sigstore](https://www.sigstore.dev). See
[release-sign.yml](.github/workflows/release-sign.yml) for details.

To verify a downloaded release at a given tag:

    % pip install sigstore
    % sigstore verify github --cert-identity https://github.com/AcademySoftwareFoundation/rez/.github/workflows/release-sign.yml@refs/tags/<tag> rez-<tag>.tar.gz

## Security Expectations

### Software Features

- The rez project implements a package management solution that is agnostic
  to build system, shell, platform, architecture, operating system, or
  packaged toolset. rez can be used to package python, javascript, C++, or
  even binaries. As long as it is possible to express the way your package
  modifies the environment to expose itself to be consumed, rez can package it.

- rez is implemented in python, and consists primarily of simply its own
  source, a handful of vendored python packages, and is installed to a system
  in the form of a virtualenv-powered executable, tied to a python interpreter.

- rez exposes a robust CLI which can be used to do common operations like build
  or release packages, to resolve and drop into a shell for a given environment,
  or to freeze context files that can be used to bake and reuse resolves.

- rez exposes an API that can be used, in and out of isolation, to perform many
  of the same tasks, as well as more granular operations, so that groups can
  also leverage many of the low-level constructs that make the higher-level CLI
  usages possible. An important disclaimer is that the rez API has not yet been
  robustly reviewed and modified to express what the boundaries of the public vs
  private API are, meaning that some internals may currently be exposed that rez
  may in the future be moved, hidden, or removed.
  
- rez reads and writes to/from stdout, as well as to/from json-like rxt files.
  rez also writes temporary shell context files like .sh or .bat scripts on a
  shell-by-shell basis, as a shell entrypoint into the chosen environment.

- rez exposes a rich plugin system which can be used and configured in order to
  augment and expand its use-cases or integrations per the users preferences.

- rez will engage in network calls only if configured to do so. Typically, this
  would be the case with the built-in `memcached` functionality, or to publish
  `amqp` messages on package release.

- The only login credentials that rez currently expects to come into contact
  with are those needed for the context tracking feature, where the amqp userid
  and password are encoded in a dictionary to be used when making the amqp
  connection.

- rez does not handle, or expect to handle, any other sort of login credentials
  to any network, file system, or verson-control system currently. rez expects
  that these details are handled independently and outside of rez.

- rez packages and plugins can, by definition and by design, result in the
  execution of arbitrary code. It is critical that users of rez maintain their
  own strict control over their own package repositories, configs, and not trust
  arbitrary packages or plugins given to them by unknown sources. rez takes no
  responsibility for malicious effects caused by that execution of code.
  
### Software Dependencies

rez depends on python and virtualenv, in order to be installed.

At runtime, without any user-provided plugins, rez depends on the following
table of vendored packages, their versions, and details related to any
modifications made:

[Vendored Packages](https://github.com/AcademySoftwareFoundation/rez/blob/main/src/rez/vendor/README.md)

### Potential Vulnerabilities

It is expected that maliciously crafted packages, or rxt files, could cause any
type of issue that would ordinarily be causable as the result of a json file load,
or an arbitrary code execution. Do not use or consume packages or context files
provided from untrusted sources without undue validation, care, or sandboxing.

#### Development Cycle and Distribution

rez is downloadable and buildable as (mostly) python source via the GitHub
releases page. Only members of the project's Technical Steering Committee have
write permissions on the source code repository. All critical software changes
are reviewed by at least one TSC member.

rez is also distributed as a [PyPI](https://pypi.org/project/rez/) package,
however this distribution is not yet usable as a so-called "production install",
for which details can be found in the
[docs](https://rez.readthedocs.io/en/stable/installation.html#installation-via-pip).
This may change in the future.
