from rez import __version__, module_root_path
from rez.config import Resolver
from rez.system import system
from rez.settings import settings
from rez.util import columnise, convert_old_commands, shlex_join, \
    mkdtemp_, rmdtemp
from rez.rex import RexExecutor, Python
from rez.shells import create_shell, get_shell_types
import pickle
import getpass
import inspect
import time
import sys
import os
import os.path



class ResolvedContext(object):
    """
    The main Rez entry point for creating, saving, loading and executing
    resolved environments. A ResolvedContext object can be saved to file and
    loaded at a later date, and it can reconstruct the equivalent environment
    at that time. It can spawn interactive and non-interactive shells, in any
    supported shell plugin type, such as bash and tcsh. It can also run a
    command within a configured python namespace, without spawning a child
    shell.
    """

    # This must be updated when the ResolvedContext class, or any class used by
    # it, changes. A minor version update means that data has been added, but it
    # can still be read by an earlier Rez version, and a major version update
    # means that backwards compatibility has been broken.
    serialize_version = (1,0)

    def __init__(self, \
        requested_packages,
        resolve_mode='latest',
        quiet=False,
        verbosity=0,
        max_fails=-1,
        timestamp=0,
        build_requires=False,
        assume_dt=False,
        caching=True,
        package_paths=None,
        add_implicit_packages=True):
        """
        Perform a package resolve, and store the result.
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
        """
        # serialization version
        self.serialize_ver = self.serialize_version

        # resolving settings
        self.req_packages = requested_packages
        self.resolve_mode = resolve_mode
        self.request_time = timestamp
        self.build_requires = build_requires
        self.assume_dt = assume_dt
        self.caching = caching
        self.package_paths = package_paths
        self.add_implicit_packages = add_implicit_packages

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

        # do the resolve
        resolver = Resolver( \
            resolve_mode=resolve_mode,
            quiet=quiet,
            verbosity=verbosity,
            max_fails=max_fails,
            time_epoch=timestamp,
            build_requires=build_requires,
            assume_dt=assume_dt,
            caching=caching,
            package_paths=package_paths)

        self.result = resolver.resolve(self.req_packages, \
            no_os=(not self.add_implicit_packages),
            meta_vars=['tools'],
            shallow_meta_vars=['tools'])

    @property
    def requested_packages(self):
        """ str list of initially requested packages, not including implicit
        packages """
        return self.req_packages

    @property
    def added_implicit_packages(self):
        """ str list of packages implicitly added to the request list """
        return self.implicit_packages if self.add_implicit_packages else []

    @property
    def resolved_packages(self):
        """ list of `ResolvedPackage` objects representing the resolve """
        return self.result.package_resolves

    @property
    def resolve_graph(self):
        """ dot-graph string representing the resolve process """
        return self.result.dot_graph

    def save(self, path):
        """
        Save the resolved context to file.
        """
        with open(path, 'w') as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path):
        """
        Load a resolved context from file.
        """
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
        return r

    def print_info(self, buf=sys.stdout, verbose=False):
        """
        Prints a message summarising the contents of the resolved context.
        """
        #TODO ensure that the env has the same info present as here, and run
        #both self and rez-env cli through the same common code to display.
        def _pr(s=''):
            print >> buf, s

        def _rt(t):
            if verbose:
                s = time.strftime("%a %b %d %H:%M:%S %Z %Y", time.localtime(t))
                return s + " (%d)" % int(t)
            else:
                return time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(t))

        t_str = _rt(self.created)
        _pr("resolved by %s@%s, on %s, using Rez v%s" \
            % (self.user, self.host, t_str, self.rez_version))
        if self.request_time:
            t_str = _rt(self.request_time)
            _pr("time was locked to %s" % t_str)
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
        for pkg in self.req_packages:
            _pr(pkg)
        _pr()

        _pr("resolved packages:")
        rows = []
        for pkg in self.result.package_resolves:
            tok = ''
            if not os.path.exists(pkg.root):
                tok = 'NOT FOUND'
            elif pkg.root.startswith(settings.local_packages_path):
                tok = 'local'
            rows.append((pkg.short_name(), pkg.root, tok))
        _pr('\n'.join(columnise(rows)))

    def get_environ(self, parent_environ=None):
        """
        Get the environ dict resulting from interpreting this context.
        @param parent_environ Environment to interpret the context within,
            defaults to os.environ if None.
        @returns The environment dict generated by this context, when
            interpreted in a python rex interpreter.
        """
        interpreter = Python(target_environ={}, passive=True)
        executor = RexExecutor(interpreter=interpreter, parent_environ=parent_environ)
        self._execute(executor)
        return executor.get_output()

    def get_shell_code(self, shell=None, parent_environ=None):
        """
        Get the shell code resulting from intepreting this context.
        @param shell Shell type, for eg 'bash'. If None, the current shell type
            is used.
        @param parent_environ Environment to interpret the context within,
            defaults to os.environ if None.
        """
        return self._get_shell_code(shell, parent_environ)[1]

    def apply(self, parent_environ=None):
        """
        Apply the context to the current python session - this updates os.environ
        and possibly sys.path.
        @param environ Environment to interpret the context within, defaults to
            os.environ if None.
        """
        interpreter = Python(target_environ=os.environ)
        executor = RexExecutor(interpreter=interpreter, parent_environ=parent_environ)
        self._execute(executor)

    def execute_command(self, args, parent_environ=None, **subprocess_kwargs):
        """
        Run a command within a resolved context. This only creates the context
        within python - to execute within a full context (so that aliases are
        set, for example) use execute_shell.
        @param args Command arguments, can be a string.
        @param parent_environ Environment to interpret the context within,
            defaults to os.environ if None.
        @param subprocess_kwargs Args to pass to subprocess.Popen.
        @returns a subprocess.Popen object.
        @note This does not alter the current python session.
        """
        interpreter = Python(target_environ={})
        executor = RexExecutor(interpreter=interpreter, parent_environ=parent_environ)
        self._execute(executor)
        return interpreter.subprocess(args, **subprocess_kwargs)

    def execute_shell(self, shell=None, parent_environ=None, rcfile=None,
                      norc=False, stdin=False, command=None, quiet=False,
                      get_stdout=False, get_stderr=False):
        """
        Spawn a possibly-interactive shell.
        @param shell Shell type, for eg 'bash'. If None, the current shell type
            is used.
        @param parent_environ Environment to interpret the context within,
            defaults to os.environ if None.
        @param rcfile Specify a file to source instead of shell startup files.
        @param norc If True, skip shell startup files, if possible.
        @param stdin If True, read commands from stdin, in a non-interactive shell.
        @param command If not None, execute this command in a non-interactive
            shell. Can be a list of args.
        @param quiet If True, skip the welcome message in interactive shells.
        @param get_stdout Capture stdout.
        @param get_stderr Capture stderr.
        @returns (returncode, stdout, stderr), where stdout/err are None if the
            corresponding get_stdxxx param was False.
        """
        if hasattr(command, "__iter__"):
            command = shlex_join(command)

        sh,context_code = self._get_shell_code(shell, parent_environ)

        tmpdir = mkdtemp_()
        context_file = os.path.join(tmpdir, "context.%s" % sh.file_extension())
        with open(context_file, 'w') as f:
            f.write(context_code)

        # spawn the shell subprocess and block until it completes
        r = sh.spawn_shell(context_file,
                           rcfile=rcfile,
                           norc=norc,
                           stdin=stdin,
                           command=command,
                           quiet=quiet,
                           get_stdout=get_stdout,
                           get_stderr=get_stderr)
        # clean up
        rmdtemp(tmpdir)
        return r

    def save_resolve_graph(self, path, fmt=None, image_ratio=None,
                           prune_to_package=None):
        """
        Write the resolve graph to an image or dot file.
        @param path File to write to.
        @param fmt File format, determined from path ext if None.
        @param image_ratio Image height / image width.
        @param prune_to_package Only display nodes dependent (directly or
            indirectly) on the given package (str).
        """
        from rez.dot import save_graph
        save_graph(self.resolve_graph, path,
                   fmt=fmt,
                   image_ratio=image_ratio,
                   prune_to_package=prune_to_package)

    def _get_shell_code(self, shell, parent_environ):
        # create the shell
        from rez.shells import create_shell
        sh = create_shell(shell or system.shell)

        # interpret this context and write out the native context file
        executor = RexExecutor(interpreter=sh, parent_environ=parent_environ)
        self._execute(executor)
        context_code = executor.get_output()

        return sh,context_code

    def _execute(self, executor):
        def _stringify_pkgs(pkgs):
            return ' '.join(x.short_name() for x in pkgs)

        def _commands_err(e, pkg_res):
            msg = "Error in commands in file %s:\n%s" % (pkg_res.metafile, str(e))
            raise PkgCommandError(msg)

        executor.update_env({
            "REZ_USED":             self.rez_path,
            "REZ_PREV_REQUEST":     "$REZ_REQUEST",
            "REZ_PACKAGES_PATH":    "$REZ_PACKAGES_PATH",
            "REZ_REQUEST":          _stringify_pkgs(self.result.package_requests),
            "REZ_RAW_REQUEST":      _stringify_pkgs(self.result.raw_package_requests),
            "REZ_RESOLVE":          _stringify_pkgs(self.result.package_resolves),
            "REZ_RESOLVE_MODE":     self.result.resolve_mode,
            "REZ_FAILED_ATTEMPTS":  self.result.failed_attempts,
            "REZ_REQUEST_TIME":     self.result.request_timestamp})

        manager = executor.manager

        # TODO set metavars, shallow_metavars
        for pkg_res in self.result.package_resolves:
            manager.comment("")
            manager.comment("Commands from package %s" % pkg_res.short_name())

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
                # old-style
                if isinstance(commands, list):
                    if settings.warn_old_commands:
                        print_warning_once("%s is using old-style commands."
                                           % pkg_res.short_name())
                    expansions = []
                    expansions.append(("!VERSION!", str(pkg_res.version)))
                    if len(pkg_res.version.parts):
                        expansions.append(("!MAJOR_VERSION!",
                                           str(pkg_res.version.major)))
                        if len(pkg_res.version.parts) > 1:
                            expansions.append(("!MINOR_VERSION!",
                                               str(pkg_res.version.minor)))
                    expansions.append(("!BASE!", str(pkg_res.base)))
                    expansions.append(("!ROOT!", str(pkg_res.root)))
                    expansions.append(("!USER!", getpass.getuser()))

                    cmds = []
                    for cmd in commands:
                        for find,replace in expansions:
                            cmd = cmd.replace(find, replace)
                        cmds.append(cmd)
                    commands = cmds

                    # testing
                    print 'OLD-------------------------------------------------'
                    print '\n'.join(commands)
                    print 'NEW-------------------------------------------------'
                    # convert to rex in a string
                    commands = convert_old_commands(commands)
                    print commands
                    print '----------------------------------------------------'

                # new-style rex code in package.yaml
                if isinstance(commands, basestring):
                    try:
                        executor.execute_code(commands, pkg_res.metafile)
                    except Exception as e:
                        _commands_err(e, pkg_res)
                # new-style rex code in package.py
                elif inspect.isfunction(commands):
                    try:
                        executor.execute_function(commands)
                    except Exception as e:
                        _commands_err(e, pkg_res)
                else:
                    _commands_err("Not a valid command section", pks_res)
