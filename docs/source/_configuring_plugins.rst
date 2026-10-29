.. py:data:: plugins.build_system

   .. py:data:: plugins.build_system.cmake

      .. py:data:: plugins.build_system.cmake.build_system
         :type: str

         CMake generator family to use. The default is ``make`` on POSIX systems
         and ``nmake`` on other systems. Valid values are ``eclipse``,
         ``codeblocks``, ``make``, ``nmake``, ``mingw``, ``xcode``,
         and ``ninja``.

      .. py:data:: plugins.build_system.cmake.build_target
         :type: str
         :value: "Release"

         CMake build configuration. Valid values are ``Debug``, ``Release``,
         and ``RelWithDebInfo``.

      .. py:data:: plugins.build_system.cmake.cmake_args
         :type: list[str]

         Arguments passed to CMake by default.

         Default:

         .. code-block:: python

            ["-Wno-dev", "--no-warn-unused-cli"]

      .. py:data:: plugins.build_system.cmake.cmake_binary
         :type: str | None
         :value: None

         Explicit CMake executable. When None, rez finds CMake on ``PATH``.

      .. py:data:: plugins.build_system.cmake.make_binary
         :type: str | None
         :value: None

         Explicit build-tool executable. When None, rez determines it from
         ``build_system``.

      .. py:data:: plugins.build_system.cmake.install_pyc
         :type: bool
         :value: True

         Install bytecode files when the ``rez_install_python`` CMake macro is used.

.. py:data:: plugins.package_repository

   .. py:data:: plugins.package_repository.filesystem

      .. py:data:: plugins.package_repository.filesystem.file_lock_type
         :type: str
         :value: "default"

         Mechanism used to create package-repository lock files. Valid values are
         ``default``, ``mkdir``, ``link``, and ``symlink``. ``default``
         uses hard links when available and otherwise uses a directory.

      .. py:data:: plugins.package_repository.filesystem.file_lock_timeout
         :type: int
         :value: 10

         Number of seconds to wait when creating a lock. Zero disables the timeout.

      .. py:data:: plugins.package_repository.filesystem.file_lock_dir
         :type: str | None
         :value: None

         Relative directory beneath the repository in which lock files are created.
         When None, locks are created in the repository root. ``.lock`` is the
         recommended directory name when a separate lock directory is needed.

      .. py:data:: plugins.package_repository.filesystem.check_package_definition_files
         :type: bool
         :value: False

         Verify that a potential package directory contains a package definition
         before treating it as a package. Enabling this is safer when repositories
         contain unrelated directories, but requires additional filesystem stats.

      .. py:data:: plugins.package_repository.filesystem.package_filenames
         :type: list[str]

         Package-definition filenames, in lookup order. The first name is also used
         for installed and released package definitions, regardless of the source
         definition's filename.

         Default:

         .. code-block:: python

            ["package"]

.. py:data:: plugins.release_hook

   .. py:data:: plugins.release_hook.amqp

      .. py:data:: plugins.release_hook.amqp.host
         :type: str
         :value: ""

         Broker hostname, optionally in ``host:port`` form.

      .. py:data:: plugins.release_hook.amqp.userid
         :type: str
         :value: ""

         Broker user ID.

      .. py:data:: plugins.release_hook.amqp.password
         :type: str
         :value: ""

         Broker password.

      .. py:data:: plugins.release_hook.amqp.connect_timeout
         :type: int
         :value: 10

         Broker connection timeout in seconds.

      .. py:data:: plugins.release_hook.amqp.exchange_name
         :type: str
         :value: ""

         Exchange to which release messages are published.

      .. py:data:: plugins.release_hook.amqp.exchange_routing_key
         :type: str
         :value: "REZ.PACKAGE.RELEASED"

         Routing key used for release messages.

      .. py:data:: plugins.release_hook.amqp.message_delivery_mode
         :type: int
         :value: 1

         AMQP delivery mode used for release messages.

      .. py:data:: plugins.release_hook.amqp.message_attributes
         :type: dict
         :value: {}

         Additional attributes added to each published message.

   .. py:data:: plugins.release_hook.command

      .. py:data:: plugins.release_hook.command.print_commands
         :type: bool
         :value: True

         Print commands before running them.

      .. py:data:: plugins.release_hook.command.print_output
         :type: bool
         :value: True

         Print command output.

      .. py:data:: plugins.release_hook.command.print_error
         :type: bool
         :value: True

         Print failed commands to standard error.

      .. py:data:: plugins.release_hook.command.cancel_on_error
         :type: bool
         :value: True

         Cancel the package release when a pre-build or pre-release command fails.

      .. py:data:: plugins.release_hook.command.stop_on_error
         :type: bool
         :value: True

         Skip the remaining commands in the current command list after a failure.
         This setting does not itself cancel the package release.

      .. py:data:: plugins.release_hook.command.pre_build_commands
         :type: list[dict]
         :value: []

         Commands to run before the package build.

      .. py:data:: plugins.release_hook.command.pre_release_commands
         :type: list[dict]
         :value: []

         Commands to run before the package release.

      .. py:data:: plugins.release_hook.command.post_release_commands
         :type: list[dict]
         :value: []

         Commands to run after the package release.

      Each entry in a command list is a mapping with a required ``command`` string
      and these optional keys:

      * ``args``: a space-separated string or list of strings;
      * ``pretty_args``: whether to format top-level lists without Python list
        syntax (default: ``True``);
      * ``user``: user under which to run the command. The current user (the
        default) and ``root``, via ``sudo``, are supported;
      * ``env``: environment variables to add to the command's environment.

      Arguments in all three command lists support object formatting with
      ``package``, ``system``, ``release.path``, ``variants``, and
      ``num_variants``. Environment-variable references are also expanded.

   .. py:data:: plugins.release_hook.emailer

      .. py:data:: plugins.release_hook.emailer.smtp_host
         :type: str
         :value: ""

         SMTP server hostname. No email is sent when this is empty.

      .. py:data:: plugins.release_hook.emailer.smtp_port
         :type: int
         :value: 25

         SMTP server port.

      .. py:data:: plugins.release_hook.emailer.sender
         :type: str
         :value: "{system.user}@rez-release.com"

         Address from which release emails are sent.

      .. py:data:: plugins.release_hook.emailer.recipients
         :type: str | list[str]
         :value: []

         Recipient addresses, or the path to a recipients YAML file. A string
         containing ``@`` that is not a file path is treated as an email address.

      .. py:data:: plugins.release_hook.emailer.subject
         :type: str

         Subject template.

         Default:

         .. code-block:: text

            [rez] [release] {system.user} released {package.qualified_name}

      .. py:data:: plugins.release_hook.emailer.body
         :type: str

         Message template. The default produces a release summary containing the
         user, package, install path, previous version, rez version, variants,
         release message, and changelog.

      The ``subject`` and ``body`` strings support object formatting. Available
      objects are ``package``, ``system``, ``release`` (with ``path``, ``message``,
      ``changelog``, and ``previous_version``), and ``variants`` (with ``count``
      and newline-separated ``paths``).

.. py:data:: plugins.release_vcs

   .. py:data:: plugins.release_vcs.tag_name
      :type: str
      :value: "{qualified_name}"

      Format string used for release tags. Package attributes can be referenced
      in the string. Using only ``{version}`` is discouraged because tags can
      collide when a repository contains multiple packages.

   .. py:data:: plugins.release_vcs.releasable_branches
      :type: list[str] | None
      :value: []

      Regular expressions for branches from which releases are allowed. An empty
      list allows all branches.

   .. py:data:: plugins.release_vcs.check_tag
      :type: bool
      :value: False

      Cancel a release when the repository is already tagged at the package's
      current version. This can prevent divergent releases in multi-site setups.

   .. py:data:: plugins.release_vcs.git

      .. py:data:: plugins.release_vcs.git.allow_no_upstream
         :type: bool
         :value: False

         Allow a release from a branch that has no upstream branch.

.. py:data:: plugins.shell

   .. py:data:: plugins.shell.sh.prompt
      :type: str
      :value: ">"

   .. py:data:: plugins.shell.bash.prompt
      :type: str
      :value: ">"

   .. py:data:: plugins.shell.csh.prompt
      :type: str
      :value: ">"

   .. py:data:: plugins.shell.tcsh.prompt
      :type: str
      :value: ">"

   .. py:data:: plugins.shell.zsh.prompt
      :type: str
      :value: "%"

   .. py:data:: plugins.shell.cmd.prompt
      :type: str
      :value: "$G"

   .. py:data:: plugins.shell.powershell.prompt
      :type: str
      :value: "> $ "

   .. py:data:: plugins.shell.pwsh.prompt
      :type: str
      :value: "> $ "

   .. py:data:: plugins.shell.gitbash.prompt
      :type: str
      :value: ">"

      Prompt text added by rez.

   .. py:data:: plugins.shell.sh.executable_fullpath
      :type: str | None
      :value: None

   .. py:data:: plugins.shell.bash.executable_fullpath
      :type: str | None
      :value: None

   .. py:data:: plugins.shell.csh.executable_fullpath
      :type: str | None
      :value: None

   .. py:data:: plugins.shell.tcsh.executable_fullpath
      :type: str | None
      :value: None

   .. py:data:: plugins.shell.zsh.executable_fullpath
      :type: str | None
      :value: None

   .. py:data:: plugins.shell.cmd.executable_fullpath
      :type: str | None
      :value: None

   .. py:data:: plugins.shell.powershell.executable_fullpath
      :type: str | None
      :value: None

   .. py:data:: plugins.shell.pwsh.executable_fullpath
      :type: str | None
      :value: None

   .. py:data:: plugins.shell.gitbash.executable_fullpath
      :type: str | None
      :value: None

      Explicit path to the shell executable, as a string or None. When None, rez
      searches for the executable.

   .. py:data:: plugins.shell.cmd.additional_pathext
      :type: list[str]
      :value: [".PY"]

   .. py:data:: plugins.shell.powershell.additional_pathext
      :type: list[str]
      :value: [".PY"]

   .. py:data:: plugins.shell.pwsh.additional_pathext
      :type: list[str]
      :value: [".PY"]

      Extensions added to ``PATHEXT`` on Windows.

   .. py:data:: plugins.shell.powershell.execution_policy
      :type: str | None
      :value: None

   .. py:data:: plugins.shell.pwsh.execution_policy
      :type: str | None
      :value: None

      `PowerShell execution-policy <https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies>`_
      override. When None or empty, the system policy is left unchanged. Rez only
      passes non-empty values consisting entirely of letters and does not validate
      policy names; other values are ignored.
