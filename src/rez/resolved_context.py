from rez import __version__, module_root_path
from rez.config import Resolver
from rez.system import system
from rez.settings import settings
from rez.util import columnise, convert_old_commands, shlex_join, \
    mkdtemp_, rmdtemp, print_warning_once, _add_bootstrap_pkg_path, \
    create_forwarding_script
from rez.rex import RexExecutor, Python
from rez.shells import create_shell, get_shell_types
import pickle
import getpass
import inspect
import yaml
import time
import uuid
import sys
import os
import os.path



class ResolvedContext(object):
    """A class that resolves and stores Rez environments.

    The main Rez entry point for creating, saving, loading and executing
    resolved environments. A ResolvedContext object can be saved to file and
    loaded at a later date, and it can reconstruct the equivalent environment
    at that time. It can spawn interactive and non-interactive shells, in any
    supported shell plugin type, such as bash and tcsh. It can also run a
    command within a configured python namespace, without spawning a child
    shell.
    """

    serialize_version = (1,0)

    def __init__(self, \
        requested_packages,
        resolve_mode='latest',
        quiet=False,
        verbosity=0,
        max_fails=-1,
        timestamp=0,
        build_requires=False,
        assume_dt=True,
        caching=True,
        package_paths=None,
        add_implicit_packages=True,
        store_failure=False):
        """Perform a package resolve, and store the result.

        @param requested_packages List of package strings defining the request,
            for example ['boost-1.43+', 'python-2.6']
        @param resolve_mode One of: 'earliest', 'latest'
        @param quiet If True then hides unnecessary output
        @param verbosity Print extra debugging info. One of: 0..2
        @param max_fails Return after N failed configuration attempts
        @param timestamp Ignore packages newer than this time-date.
        @param assume_dt Assume dependency transitivity
        @param caching If True, resolve info is read from and written to a
            memcache daemon, if possible.
        @param package_paths List of paths to search for pkgs, defaults to
            settings.packages_path.
        @param add_implicit_packages If True, the implicit package list
            defined by settings.implicit_packages is added to the request.
        @param store_failure If True, this context will store a resolve failure,
            instead of raising the associated exception. In the event of failure,
            self.success is False, and self.dot_graph, if available, will
            contain a graph detailing the reason for failure.
        """
        # serialization
        self.serialize_ver = self.serialize_version
        self.load_path = None

        # resolving settings
        self.package_request_strings = requested_packages
        self.resolve_mode = resolve_mode
        self.request_time = timestamp
        self.build_requires = build_requires
        self.assume_dt = assume_dt
        self.caching = caching
        self.add_implicit_packages = add_implicit_packages
        # rez bootstrap path is *always* added
        pkg_paths = settings.packages_path if package_paths is None else package_paths
        self.package_paths = _add_bootstrap_pkg_path(pkg_paths)

        # info about env the resolve occurred in, useful for debugging
        self.user = getpass.getuser()
        self.host = system.fqdn
        self.platform = system.platform
        self.arch = system.arch
        self.os = system.os
        self.shell = system.shell
        self.rez_version = __version__
        self.rez_path = module_root_path
        self.implicit_packages = settings.implicit_packages
        self.created = int(time.time())

        # the resolve results
        self.success = False
        self.error_message = None
        self.package_requests = None
        self.resolved_pkgs = None
        self.dot_graph = None
        self.failed_attempts = None
        self.request_timestamp = None

        # do the resolve
        resolver = Resolver(resolve_mode=resolve_mode,
                            quiet=quiet,
                            verbosity=verbosity,
                            max_fails=max_fails,
                            time_epoch=timestamp,
                            build_requires=build_requires,
                            assume_dt=assume_dt,
                            caching=caching,
                            package_paths=self.package_paths)

        exc_type = Exception if store_failure else None
        result = None

        try:
            result = resolver.resolve(self.package_request_strings, \
                no_implicit=(not self.add_implicit_packages),
                meta_vars=['tools'],
                shallow_meta_vars=['tools'])

            self.success = True
            self.package_requests = result.package_requests
            self.resolved_pkgs = result.package_resolves
            self.failed_attempts = result.failed_attempts
            self.request_timestamp = result.request_timestamp
            self.dot_graph = result.dot_graph
        except exc_type as e:
            self.success = False
            self.error_message = str(e)
            if hasattr(e, "get_dot_graph"):
                self.dot_graph = e.get_dot_graph()

    @property
    def requested_packages(self):
        """ str list of initially requested packages, not including implicit
        packages """
        return self.package_request_strings

    @property
    def added_implicit_packages(self):
        """ str list of packages implicitly added to the request list """
        return self.implicit_packages if self.add_implicit_packages else []

    @property
    def resolved_packages(self):
        """ list of `ResolvedPackage` objects representing the resolve """
        return self.resolved_pkgs

    @property
    def resolve_graph(self):
        """ dot-graph string representing the resolve process. If this resolve
         failed, this will be a graph showing the failure, or None """
        return self.dot_graph

    def save(self, path):
        """Save the resolved context to file."""
        with open(path, 'w') as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path):
        """Load a resolved context from file."""
        def _v(t):
            return '%d.%d' % t

        curr_ver = ResolvedContext.serialize_version
        with open(path) as f:
            r = pickle.load(f)

        if r.serialize_ver < curr_ver:
            raise Exception("The version of the context (v%s) is too old, "
                "must be v%s or greater" % (_v(r.serialize_ver), _v(curr_ver)))
        if r.serialize_ver[0] > curr_ver[0]:
            next_major = (curr_ver[0]+1, 0)
            raise Exception("The version of the context (v%s) is too new - "
                "this version of Rez can only read contexts earlier than v%s" \
                % (_v(r.serialize_ver), _v(next_major)))

        r.load_path = os.path.abspath(path)
        return r

    def on_success(fn):
        def _check(self, *nargs, **kwargs):
            if self.success:
                return fn(self, *nargs, **kwargs)
            else:
                raise Exception("Cannot perform operation in a failed context")
        return _check

    @on_success
    def validate(self):
        """Check compatibility with the current system.

        For instance, a loaded context may have been created on a different host,
        with different package search paths, and so may refer to packages not
        available on the current host.
        """
        # check package paths
        for pkg in self.resolved_pkgs:
            if not os.path.exists(pkg.root):
                raise Exception("Package %s path does not exist: %s" \
                    % (pkg.short_name(), pkg.root))

        # check system packages
        # FIXME TODO

    def print_info(self, buf=sys.stdout, verbose=False):
        """Prints a message summarising the contents of the resolved context.
        """
        def _pr(s=''):
            print >> buf, s

        def _rt(t):
            if verbose:
                s = time.strftime("%a %b %d %H:%M:%S %Z %Y", time.localtime(t))
                return s + " (%d)" % int(t)
            else:
                return time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(t))

        if not self.success:
            _pr("This context contains a failed resolve:\n")
            _pr(self.error_message)
            return

        t_str = _rt(self.created)
        _pr("resolved by %s@%s, on %s, using Rez v%s" \
            % (self.user, self.host, t_str, self.rez_version))
        if self.request_time:
            t_str = _rt(self.request_time)
            _pr("packages released after %s are being ignored" % t_str)
        _pr()

        if verbose:
            _pr("search paths:")
            for path in settings.packages_path:
                _pr(path)
            _pr()

        if self.add_implicit_packages and self.implicit_packages:
            _pr("implicit packages:")
            for pkg in self.implicit_packages:
                _pr(pkg)
            _pr()

        _pr("requested packages:")
        for pkg in self.package_request_strings:
            _pr(pkg)
        _pr()

        _pr("resolved packages:")
        rows = []
        for pkg in self.resolved_pkgs:
            tok = ''
            if not os.path.exists(pkg.root):
                tok = 'NOT FOUND'
            elif pkg.root.startswith(settings.local_packages_path):
                tok = 'local'
            rows.append((pkg.short_name(), pkg.root, tok))
        _pr('\n'.join(columnise(rows)))

        if verbose:
            _pr()
            _pr("resolved after %d attempts" % self.failed_attempts)

    @on_success
    def get_environ(self, parent_environ=None):
        """Get the environ dict resulting from interpreting this context.

        @param parent_environ Environment to interpret the context within,
            defaults to os.environ if None.
        @returns The environment dict generated by this context, when
            interpreted in a python rex interpreter.
        """
        interp = Python(target_environ={}, passive=True)
        executor = self._create_executor(interp, parent_environ)
        self._execute(executor)
        return executor.get_output()

    @on_success
    def get_key(self, key, request_only=False):
        """Get a metadata key value for each resolved package.

        Args:
            key: String key of property, eg 'tools'.
            request_only: If True, only return the key from resolved packages
                that were also present in the request.

        Returns:
            Dict of {pkg-name: value}.
        """
        values = {}
        reqs = None
        if request_only:
            reqs = [x.split('-',1)[0] for x in self.package_request_strings]
            reqs = [x for x in reqs if not x.startswith('!')]
            reqs = [x for x in reqs if not x.startswith('~')]
            reqs = set(reqs)

        for pkg_res in self.resolved_pkgs:
            if (not request_only) or (pkg_res.name.split('-',1)[0] in reqs):
                val = pkg_res.metadata.get(key)
                if val is not None:
                    values[pkg_res.name] = val
        return values

    @on_success
    def get_shell_code(self, shell=None, parent_environ=None):
        """Get the shell code resulting from intepreting this context.

        @param shell Shell type, for eg 'bash'. If None, the current shell type
            is used.
        @param parent_environ Environment to interpret the context within,
            defaults to os.environ if None.
        """
        from rez.shells import create_shell
        sh = create_shell(shell)
        executor = self._create_executor(sh, parent_environ)
        self._execute(executor)
        return executor.get_output()

    @on_success
    def apply(self, parent_environ=None):
        """Apply the context to the current python session.

        Note that this updates os.environ and possibly sys.path.

        @param environ Environment to interpret the context within, defaults to
            os.environ if None.
        """
        interpreter = Python(target_environ=os.environ)
        executor = self._create_executor(interpreter, parent_environ)
        self._execute(executor)

    @on_success
    def execute_command(self, args, parent_environ=None, **subprocess_kwargs):
        """Run a command within a resolved context.

        This only creates the context within python - to execute within a full
        context (so that aliases are set, for example) use execute_shell.

        @param args Command arguments, can be a string.
        @param parent_environ Environment to interpret the context within,
            defaults to os.environ if None.
        @param subprocess_kwargs Args to pass to subprocess.Popen.
        @returns a subprocess.Popen object.
        @note This does not alter the current python session.
        """
        interpreter = Python(target_environ={})
        executor = self._create_executor(interpreter, parent_environ)
        self._execute(executor)
        return interpreter.subprocess(args, **subprocess_kwargs)

    @on_success
    def execute_shell(self, shell=None, parent_environ=None, rcfile=None,
                      norc=False, stdin=False, command=None, quiet=False,
                      block=None, actions_callback=None, context_filepath=None,
                      **Popen_args):
        """Spawn a possibly-interactive shell.

        Args:
            shell: Shell type, for eg 'bash'. If None, the current shell type
                is used.
            parent_environ: Environment to interpret the context within,
                defaults to os.environ if None.
            rcfile: Specify a file to source instead of shell startup files.
            norc: If True, skip shell startup files, if possible.
            stdin: If True, read commands from stdin, in a non-interactive shell.
            command: If not None, execute this command in a non-interactive
                shell. Can be a list of args.
            quiet: If True, skip the welcome message in interactive shells.
            block: If True, block until the shell is terminated. If False,
                return immediately. If None, will default to blocking if the
                shell is interactive.
            actions_callback: Callback with signature (RexExecutor). This lets
                the user append custom actions to the context, such as settings
                extra environment variables.
            context_filepath: If provided, the context file will be written here,
                rather than to the default location (which is in a tempdir). If
                you use this arg, you are responsible for cleaning up the file.
            popen_args: args to pass to the shell process object constructor.

        Returns:
            If blocking: A 3-tuple of (returncode, stdout, stderr);
            If non-blocking - A subprocess.Popen object for the shell process.
        """
        if hasattr(command, "__iter__"):
            command = shlex_join(command)

        # block if the shell is likely to be interactive
        if block is None:
            block = not (command or stdin)

        # create the shell
        from rez.shells import create_shell
        sh = create_shell(shell)

        # context and rxt files
        tmpdir = mkdtemp_()

        if self.load_path and os.path.isfile(self.load_path):
            rxt_file = self.load_path
        else:
            rxt_file = os.path.join(tmpdir, "context.rxt")
            self.save(rxt_file)

        context_file = context_filepath or \
                       os.path.join(tmpdir, "context.%s" % sh.file_extension())

        # interpret this context and write out the native context file
        executor = self._create_executor(sh, parent_environ)
        executor.env.REZ_RXT_FILE = rxt_file
        executor.env.REZ_CONTEXT_FILE = context_file
        if actions_callback:
            actions_callback(executor)

        self._execute(executor)
        context_code = executor.get_output()
        with open(context_file, 'w') as f:
            f.write(context_code)

        # spawn the shell subprocess
        p = sh.spawn_shell(context_file,
                           tmpdir,
                           rcfile=rcfile,
                           norc=norc,
                           stdin=stdin,
                           command=command,
                           quiet=quiet,
                           **Popen_args)
        if block:
            stdout,stderr = p.communicate()
            return p.returncode,stdout,stderr
        else:
            return p

    def create_wrapped_context(self, path, rxt_name=None, prefix=None,
                               suffix=None, request_only=True, overwrite=False,
                               verbose=False):
        """Create a 'wrapped context'.

        A wrapped context is an rxt file with a set of accompanying executable
        scripts, which wrap the tools available within the context. When a user
        runs one of these scripts, the wrapped tool is run within the context.
        This allows us to expose tools to users in unresolved environments, yet
        ensure that when the tool is executed, it does so within its correctly
        resolved environment. You can create multiple wrapped contexts within
        a single path.

        Args:
            path: Directory to create the wrapped context within. Either this
                directory or its parent must exist.
            rxt_name: Name of the rxt file to write. If None, a uuid-type string
                is generated for you. If non-None, but that file already exists
                in the path, then the name will be suffixed with '_2', '_3' etc
                until it no longer conflicts with an existing file.
            prefix: If not None, this string is prefixed to wrapped tools. For
                example, if the context contains a tool 'maya', then prefix='fx_'
                would create a user-facing tool called 'fx_maya'.
            suffix: Wrapped tool suffix, or None.
            request_only: If True, only tools from packages in the request list
                are wrapped.
            overwrite: If True, pre-existing wrapped tools within the path that
                have the same name will be overwritten.

        Returns:
            Path to a subdirectory within 'path' containing the wrapped tools,
            or None if no tools were wrapped.
        """
        path = os.path.abspath(path)
        ppath = os.path.dirname(path)
        if not os.path.isdir(ppath):
            open(ppath)  # raise IOError
        if not os.path.exists(path):
            os.mkdir(path)

        # write rxt file
        if rxt_name:
            if os.path.splitext(rxt_name)[1] != ".rxt":
                rxt_name += ".rxt"
            file = os.path.join(path, rxt_name)

            i = 2
            while os.path.exists(file):
                file = "%s_%d.rxt" % (os.path.splitext(file)[0], i)
                i += 1
            rxt_name = os.path.basename(file)
        else:
            rxt_name = str(uuid.uuid4()).replace('-','') + ".rxt"

        rxt_file = os.path.join(path, rxt_name)
        if verbose:
            print "writing %s..." % rxt_file
        self.save(rxt_file)

        # write wrapped env yaml file. This is mostly just done so that Rez can
        # know that this path contains a valid wrapped environment.
        yaml_file = os.path.join(path, "wrapped_environment.yaml")
        if not os.path.exists(yaml_file):
            doc = dict(created_by=getpass.getuser(),
                       created_at=int(time.time()))
            with open(yaml_file, 'w') as f:
                f.write(yaml.dump(doc, default_flow_style=False))

        # create wrapped tools
        keys = self.get_key("tools", request_only=request_only)
        if not keys:
            return None

        n = 0
        binpath = os.path.join(path, "bin")
        if not os.path.exists(binpath):
            os.mkdir(binpath)

        for pkg,tools in keys.iteritems():
            doc = dict(tools=[])

            for tool in tools:
                toolname = "%s%s%s" % ((prefix or ''), tool, (suffix or ''))
                doc["tools"].append([pkg, toolname])
                if verbose:
                    print "writing tool '%s' for package '%s'..." % (toolname, pkg)

                file = os.path.join(binpath, toolname)
                if os.path.exists(file) and not overwrite:
                    continue

                n += 1
                create_forwarding_script(file, "resolved_context",
                                         "_invoke_wrapped_tool",
                                         rxt_file=rxt_name,
                                         tool=tool)

            yaml_file = os.path.join(path, "%s.yaml"
                                           % os.path.splitext(rxt_name)[0])
            with open(yaml_file, 'w') as f:
                f.write(yaml.dump(doc, default_flow_style=False))

        if verbose:
            print "\n%d tools were written to %s\n" % (n, binpath)
        return binpath

    def _create_executor(self, interpreter, parent_environ):
        parent_vars = True if settings.all_parent_variables \
            else settings.parent_variables

        return RexExecutor(interpreter=interpreter,
                           parent_environ=parent_environ,
                           parent_variables=parent_vars)

    def _get_shell_code(self, shell, parent_environ):
        # create the shell
        from rez.shells import create_shell
        sh = create_shell(shell)

        # interpret this context and write out the native context file
        executor = self._create_executor(sh, parent_environ)
        self._execute(executor)
        context_code = executor.get_output()

        return sh,context_code

    def _execute(self, executor):
        def _stringify_pkgs(pkgs):
            return ' '.join(x.short_name() for x in pkgs)

        executor.update_env({
            "REZ_USED":             self.rez_path,
            # TODO add back if and when we need this
            #"REZ_PREV_REQUEST":     "$REZ_REQUEST",
            #"REZ_RAW_REQUEST":      _stringify_pkgs(self.result.raw_package_requests),
            "REZ_REQUEST":          _stringify_pkgs(self.package_requests),
            "REZ_RESOLVE":          _stringify_pkgs(self.resolved_pkgs),
            "REZ_RESOLVE_MODE":     self.resolve_mode,
            "REZ_FAILED_ATTEMPTS":  self.failed_attempts,
            "REZ_REQUEST_TIME":     self.request_timestamp})

        executor.bind('building', bool(os.getenv('REZ_BUILD_ENV')))

        manager = executor.manager

        for pkg_res in self.resolved_pkgs:
            manager.comment("")
            manager.comment("Commands from package %s" % pkg_res.short_name())
            manager.comment("")

            prefix = "REZ_" + pkg_res.name.upper()
            executor.update_env({
                prefix+"_VERSION":  pkg_res.version,
                prefix+"_BASE":     pkg_res.base,
                prefix+"_ROOT":     pkg_res.root})

            executor.bind('this', pkg_res)
            executor.bind('root', pkg_res.root)
            executor.bind('base', pkg_res.base)
            executor.bind('version', pkg_res.version)

            commands = pkg_res.metadata.get("commands")
            if commands:
                # old-style, we convert it to a rex code string (ie python)
                if isinstance(commands, list):
                    if settings.warn_old_commands:
                        print_warning_once("%s is using old-style commands."
                                           % pkg_res.short_name())

                    # convert expansions from !OLD! style to {new}
                    cmds = []
                    for cmd in commands:
                        cmd = cmd.replace("!VERSION!",      "{version}")
                        cmd = cmd.replace("!MAJOR_VERSION!","{version.major}")
                        cmd = cmd.replace("!MINOR_VERSION!","{version.minor}")
                        cmd = cmd.replace("!BASE!",         "{base}")
                        cmd = cmd.replace("!ROOT!",         "{root}")
                        cmd = cmd.replace("!USER!",         "{user}")
                        cmds.append(cmd)
                    commands = convert_old_commands(cmds)

                try:
                    if isinstance(commands, basestring):
                        # rex code in a string
                        executor.execute_code(commands, pkg_res.metafile)
                    elif inspect.isfunction(commands):
                        # function in a package.py
                        executor.execute_function(commands)
                except Exception as e:
                    msg = "Error in commands in file %s:\n%s" \
                          % (pkg_res.metafile, str(e))
                    raise PkgCommandError(msg)


def _invoke_wrapped_tool(rxt_file, tool, _script, _cli_args):
    path = os.path.join(os.path.dirname(_script), "..", rxt_file)
    context = ResolvedContext.load(path)
    cmd = [tool] + _cli_args

    retcode,_,_ = context.execute_shell(command=cmd, block=True)
    sys.exit(retcode)
