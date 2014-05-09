from rez import __version__, module_root_path
from rez.resolver import Resolver
from rez.system import system
from rez.settings import settings
from rez.util import columnise, convert_old_commands, shlex_join, \
    mkdtemp_, rmdtemp, print_warning_once, _add_bootstrap_pkg_path, \
    create_forwarding_script, is_subdirectory
from rez.contrib.pygraph.readwrite.dot import write as write_dot
from rez.contrib.pygraph.readwrite.dot import read as read_dot
from rez.contrib.version.requirement import Requirement
from rez.rex import RexExecutor, Python
from rez.rex_bindings import VersionBinding, VariantBinding, \
    VariantsBinding, RequirementsBinding
from rez.packages import Variant
from rez.shells import create_shell, get_shell_types
from rez.exceptions import RezSystemError, PackageCommandError
from rez.contrib import yaml
import getpass
import inspect
import time
import uuid
import sys
import os
import os.path



class ResolvedContext(object):
    """A class that resolves, stores and spawns Rez environments.

    The main Rez entry point for creating, saving, loading and executing
    resolved environments. A ResolvedContext object can be saved to file and
    loaded at a later date, and it can reconstruct the equivalent environment
    at that time. It can spawn interactive and non-interactive shells, in any
    supported shell plugin type, such as bash and tcsh. It can also run a
    command within a configured python namespace, without spawning a child
    shell.
    """
    serialize_version = 0

    def __init__(self, \
        package_requests,
        quiet=False,
        verbosity=0,
        timestamp=0,
        building=False,
        caching=True,
        package_paths=None,
        add_implicit_packages=True,
        add_bootstrap_path=None):
        """Perform a package resolve, and store the result.

        Args:
            package_requests: List of strings or Requirement objects
                representing the request.
            quiet: If True then hides unnecessary output
            verbosity: Verbosity level. One of [0,1,2].
            timestamp: Ignore packages newer than this time-date.
            building: True if we're resolving for a build.
            caching: If True, cache(s) may be used to speed the resolve.
            package_paths: List of paths to search for pkgs, defaults to
                settings.packages_path.
            add_implicit_packages: If True, the implicit package list defined by
                settings.implicit_packages is added to the request.
            add_bootstrap_path: If True, append the package search path with
                the bootstrap path. If False, do not append. If None, use the
                default specified in settings.add_bootstrap_path.
        """
        self.load_path = None

        # resolving settings
        self.timestamp = timestamp
        self.building = building
        self.caching = caching
        self.implicit_packages = []

        self.package_requests = []
        for req in package_requests:
            if isinstance(req, basestring):
                req = Requirement(req)
            self.package_requests.append(req)

        self.package_paths = settings.packages_path \
            if package_paths is None else package_paths
        if add_bootstrap_path or \
            (add_bootstrap_path is None and settings.add_bootstrap_path):
            self.package_paths = _add_bootstrap_pkg_path(self.package_paths)

        if add_implicit_packages:
            pkg_strs = settings.implicit_packages
            self.implicit_packages = [Requirement(x) for x in pkg_strs]
            self.package_requests = self.implicit_packages + self.package_requests

        # info about env the resolve occurred in
        self.rez_version = __version__
        self.rez_path = module_root_path
        self.user = getpass.getuser()
        self.host = system.fqdn
        self.platform = system.platform
        self.arch = system.arch
        self.os = system.os
        self.created = int(time.time())

        # resolve results
        self.status = "pending"
        self.resolved_packages_ = None
        self.failure_description = None
        self.graph_string = None
        self.graph_ = None
        self.solve_time = 0.0
        self.load_time = 0.0

        # perform the solve
        def _pr(s):
            print s
            return True

        verbose_ = False
        callback = None
        if verbosity >= 2:
            verbose_ = True
        elif verbosity == 1:
            callback = _pr

        resolver = Resolver(package_requests=self.package_requests,
                            package_paths=self.package_paths,
                            caching=caching,
                            callback=callback,
                            verbose=verbose_)
        resolver.solve()

        # convert the results
        self.status = resolver.status
        self.solve_time = resolver.solve_time
        self.load_time = resolver.load_time

        if resolver.graph is not None:
            self.graph_ = resolver.graph

        if self.status == "solved":
            # convert solver.Variants to packages.Variants
            pkgs = []
            for variant in resolver.resolved_packages:
                pkg = Variant(name=variant.name,
                              version=variant.version,
                              path=variant.metafile,
                              index=variant.index)

                pkgs.append(pkg)
            self.resolved_packages_ = pkgs
        elif self.status == "failed":
            self.failure_description = resolver.failure_description

    @property
    def resolved_packages(self):
        """Returns List of `Variant` objects representing the resolve, or None
        if the resolve was unsuccessful."""
        return self.resolved_packages_

    @property
    def has_graph(self):
        """Return True if the resolve has a graph."""
        return ((self.graph_ is not None) or self.graph_string)

    def get_resolved_package(self, name):
        """Returns a Variant object or None if the package is not in the resolve.
        """
        pkgs = [x for x in self.resolved_packages_ if x.name == name]
        return pkgs[0] if pkgs else None

    def graph(self, as_dot=False):
        """Get the resolve graph.

        Args:
            as_dot: If True, get the graph as a dot-language string. Otherwise,
                a pygraph.digraph object is returned.

        Returns:
            A string or pygraph.digraph object, or None if there is no graph
            associated with the resolve.
        """
        if not self.has_graph:
            return None
        elif as_dot:
            if not self.graph_string:
                self.graph_string = write_dot(self.graph_)
            return self.graph_string
        elif self.graph_ is None:
            self.graph_ = read_dot(self.graph_string)

        return self.graph_

    def save(self, path):
        """Save the resolved context to file."""
        doc = self.to_dict()
        content = yaml.dump(doc)
        with open(path, 'w') as f:
            f.write(content)

    @classmethod
    def load(cls, path):
        """Load a resolved context from file."""
        with open(path) as f:
            doc = yaml.load(f.read())

        load_ver = doc["serialize_version"]
        curr_ver = ResolvedContext.serialize_version
        if load_ver > curr_ver:
            raise RezSystemError(("The context stored in %s cannot be " + \
                "loaded, because it was written by a newer version of Rez " + \
                "(serialize version %d > %d)") % (path, load_ver, curr_ver))

        r = cls.from_dict(doc)
        r.load_path = os.path.abspath(path)
        return r

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

        if self.status in ("failed", "aborted"):
            _pr("The context failed to resolve:\n")
            _pr(self.failure_description)
            return

        t_str = _rt(self.created)
        _pr("resolved by %s@%s, on %s, using Rez v%s" \
            % (self.user, self.host, t_str, self.rez_version))
        if self.timestamp:
            t_str = _rt(self.timestamp)
            _pr("packages released after %s were ignored" % t_str)
        _pr()

        if verbose:
            _pr("search paths:")
            for path in self.package_paths:
                _pr(path)
            _pr()

        _pr("requested packages:")
        for pkg in self.package_requests:
            _pr(str(pkg))
        _pr()

        _pr("resolved packages:")
        rows = []
        for pkg in self.resolved_packages:
            tok = ''
            if not os.path.exists(pkg.root):
                tok = 'NOT FOUND'
            elif is_subdirectory(pkg.root, settings.local_packages_path):
                tok = '(local)'
            rows.append((pkg.qualified_package_name, pkg.root, tok))
        _pr('\n'.join(columnise(rows)))

        if verbose:
            _pr()
            _pr("resolve details:")
            _pr("load time: %.02f secs" % self.load_time)
            _pr("solve time: %.02f secs" % self.solve_time)

    def _on_success(fn):
        def _check(self, *nargs, **kwargs):
            if self.status == "solved":
                return fn(self, *nargs, **kwargs)
            else:
                raise RezSystemError("Cannot perform operation in a failed context")
        return _check

    @_on_success
    def validate(self):
        """Check compatibility with the current system.

        For instance, a loaded context may have been created on a different host,
        with different package search paths, and so may refer to packages not
        available on the current host.
        """
        # check package paths
        for pkg in self.resolved_packages:
            if not os.path.exists(pkg.root):
                raise RezSystemError("Package %s path does not exist: %s" \
                    % (pkg.qualified_package_name, pkg.root))

    @_on_success
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

    @_on_success
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
        requested_names = [x.name for x in self.package_requests if not x.conflict]

        for pkg in self.resolved_packages:
            if (not request_only) or (pkg.name in requested_names):
                value = pkg.metadata.get(key)
                if value is not None:
                    values[pkg.name] = value

        return values

    @_on_success
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

    @_on_success
    def get_actions(self, parent_environ=None):
        """Get the list of rex.Action objects resulting from interpreting this
        context. This is provided mainly for testing purposes.

        Args:
            parent_environ Environment to interpret the context within,
                defaults to os.environ if None.

        Returns:
            A list of rex.Action subclass instances.
        """
        interp = Python(target_environ={}, passive=True)
        executor = self._create_executor(interp, parent_environ)
        self._execute(executor)
        return executor.actions

    @_on_success
    def apply(self, parent_environ=None):
        """Apply the context to the current python session.

        Note that this updates os.environ and possibly sys.path.

        @param environ Environment to interpret the context within, defaults to
            os.environ if None.
        """
        interpreter = Python(target_environ=os.environ)
        executor = self._create_executor(interpreter, parent_environ)
        self._execute(executor)

    @_on_success
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

    @_on_success
    def execute_shell(self, shell=None, parent_environ=None, rcfile=None,
                      norc=False, stdin=False, command=None, quiet=False,
                      block=None, actions_callback=None, context_filepath=None,
                      **Popen_args):
        """Spawn a possibly-interactive shell.

        Args:
            shell: Shell type, for eg 'bash'. If None, the current shell type
                is used.
            parent_environ: Environment to run the shell process in, if None
                then the current environment is used.
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
                           env=parent_environ,
                           quiet=quiet,
                           **Popen_args)
        if block:
            stdout,stderr = p.communicate()
            return p.returncode,stdout,stderr
        else:
            return p

    # TODO rename to "create_suite"
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
                                         "_FWD__invoke_wrapped_tool",
                                         rxt_file=rxt_name,
                                         tool=tool)

            yaml_file = os.path.join(path, "%s.yaml"
                                           % os.path.splitext(rxt_name)[0])
            with open(yaml_file, 'w') as f:
                f.write(yaml.dump(doc, default_flow_style=False))

        if verbose:
            print "\n%d tools were written to %s\n" % (n, binpath)
        return binpath

    def to_dict(self):
        resolved_packages = [x.to_dict() for x in self.resolved_packages_] \
            if self.resolved_packages_ else None

        return dict(
            serialize_version=ResolvedContext.serialize_version,

            timestamp=self.timestamp,
            building=self.building,
            caching=self.caching,
            implicit_packages=[str(x) for x in self.implicit_packages],
            package_requests=[str(x) for x in self.package_requests],
            package_paths=self.package_paths,

            rez_version=self.rez_version,
            rez_path=self.rez_path,
            user=self.user,
            host=self.host,
            platform=self.platform,
            arch=self.arch,
            os=self.os,
            created=self.created,

            status=self.status,
            resolved_packages=resolved_packages,
            failure_description=self.failure_description,
            graph=self.graph(as_dot=True),
            solve_time=self.solve_time,
            load_time=self.load_time)

    @classmethod
    def from_dict(cls, d):
        r = ResolvedContext.__new__(ResolvedContext)
        sz_ver = d["serialize_version"]  # for backwards compatibility
        r.load_path = None

        resolved_packages = d["resolved_packages"]

        r.timestamp = d["timestamp"]
        r.building = d["building"]
        r.caching = d["caching"]
        r.implicit_packages = [Requirement(x) for x in d["implicit_packages"]]
        r.package_requests = [Requirement(x) for x in d["package_requests"]]
        r.package_paths = d["package_paths"]

        r.rez_version = d["rez_version"]
        r.rez_path = d["rez_path"]
        r.user = d["user"]
        r.host = d["host"]
        r.platform = d["platform"]
        r.arch = d["arch"]
        r.os = d["os"]
        r.created = d["created"]

        r.status = d["status"]
        r.resolved_packages_ = [Variant.from_dict(x) for x in resolved_packages] \
            if resolved_packages else None
        r.failure_description = d["failure_description"]
        r.solve_time = d["solve_time"]
        r.load_time = d["load_time"]

        r.graph_string = d["graph"]
        r.graph_ = None

        return r

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
        """
        executor.update_env({
            "REZ_USED":             self.rez_path,
            # TODO add back if and when we need this
            #"REZ_PREV_REQUEST":     "$REZ_REQUEST",
            #"REZ_RAW_REQUEST":      _stringify_pkgs(self.result.raw_package_requests),
            #"REZ_RESOLVE_MODE":     self.resolve_mode,
            #"REZ_FAILED_ATTEMPTS":  self.failed_attempts,
            "REZ_REQUEST":          request_str,
            "REZ_RESOLVE":          resolve_str,
            # TODO FIXME this should be actual timestamp used even if timestamp not
            # speicified, but the new solver doesnt do this yet.
            "REZ_REQUEST_TIME":     self.timestamp})
        """

        # bind various info to the execution context
        executor.setenv("REZ_USED", self.rez_path)
        # TODO FIXME this should be actual timestamp used even if timestamp not specified
        executor.setenv("REZ_REQUEST_TIME", self.timestamp)

        resolved_pkgs = self.resolved_packages or []
        request_str = ' '.join(str(x) for x in self.package_requests)
        resolve_str = ' '.join(x.qualified_package_name for x in resolved_pkgs)

        executor.setenv("REZ_REQUEST", request_str)
        executor.setenv("REZ_RESOLVE", resolve_str)

        executor.bind('building', bool(os.getenv('REZ_BUILD_ENV')))
        executor.bind('request', RequirementsBinding(self.package_requests))
        executor.bind('resolve', VariantsBinding(resolved_pkgs))

        # apply each resolved package to the execution context
        for pkg in resolved_pkgs:
            executor.comment("")
            executor.comment("Commands from package %s" % pkg.qualified_name)
            executor.comment("")

            prefix = "REZ_" + pkg.name.upper()
            executor.setenv(prefix+"_VERSION", str(pkg.version))
            executor.setenv(prefix+"_BASE", pkg.base)
            executor.setenv(prefix+"_ROOT", pkg.root)

            executor.bind('this',       VariantBinding(pkg))
            executor.bind("version",    VersionBinding(pkg.version))
            executor.bind('root',       pkg.root)
            executor.bind('base',       pkg.base)

            commands = pkg.metadata.get("commands")
            if commands:
                # old-style, we convert it to a rex code string (ie python)
                if isinstance(commands, list):
                    if settings.warn("old_commands"):
                        print_warning_once("%s is using old-style commands."
                                           % pkg.qualified_name)

                    # convert expansions from !OLD! style to {new}
                    cmds = []
                    for cmd in commands:
                        cmd = cmd.replace("!VERSION!",       "{version}")
                        cmd = cmd.replace("!MAJOR_VERSION!", "{version.major}")
                        cmd = cmd.replace("!MINOR_VERSION!", "{version.minor}")
                        cmd = cmd.replace("!BASE!",          "{base}")
                        cmd = cmd.replace("!ROOT!",          "{root}")
                        cmd = cmd.replace("!USER!",          "{user}")
                        cmds.append(cmd)
                    commands = convert_old_commands(cmds)

                try:
                    if isinstance(commands, basestring):
                        # rex code is in a string
                        executor.execute_code(commands, pkg.metafile)
                    elif inspect.isfunction(commands):
                        # rex code is a function in a package.py
                        executor.execute_function(commands)
                except Exception as e:
                    msg = "Error in commands in file %s:\n%s" \
                          % (pkg.metafile, str(e))
                    raise PackageCommandError(msg)


def _FWD__invoke_wrapped_tool(rxt_file, tool, _script, _cli_args):
    path = os.path.join(os.path.dirname(_script), "..", rxt_file)
    context = ResolvedContext.load(path)
    cmd = [tool] + _cli_args

    retcode,_,_ = context.execute_shell(command=cmd, block=True)
    sys.exit(retcode)
