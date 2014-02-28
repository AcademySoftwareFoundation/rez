from rez import plugin_factory
from rez.source_retrieval import RepoCloner



class HgCloner(RepoCloner):
    @classmethod
    def name(cls):
        return "hg"

    @classmethod
    def supported_url_types(cls):
        return ['.hg']

    @classmethod
    def repo_current_symbol(cls, repo_dir):
        '''Returns the symbol that represents the "current" revision
        '''
        return "."

    def hg(self, repo_dir, hg_args, get_stdout=False, get_stderr=False,
            check_return=True, quiet=True, **subprocess_kwargs):
        '''Run an hg command for the given repo_dir, with the given args

        Parameters
        ----------
        repo_dir : basestring or None
            if non-None, a mercurial working dir to set as the repo to use; note
            that since this is a required argument, if you wish to run an hg
            command that does not need a current repository (ie, 'hg --version',
            'hg clone', etc), you must explicitly pass None
        hg_args : strings
            args to pass to hg (as on the command line)
        wait : if True, then the result of subprocess.call is returned (ie,
            we wait for the process to finish, and return the returncode); if
            False, then the result of subprocess.Popen is returned (ie, we do
            not wait for the process to finish, and return the Popen object)
        check_return:
            if wait is True, and check_return is True, then an error will be
            raised if the return code is non-zero
        subprocess_kwargs : strings
            keyword args to pass to subprocess.call
        '''
        args = ['hg']
        if repo_dir is not None:
            args.extend(['-R', repo_dir])
        args.extend(hg_args)
        return self._subprocess(args,
                                get_stdout=get_stdout,
                                get_stderr=get_stderr,
                                check_return=check_return,
                                quiet=quiet,
                                **subprocess_kwargs)

    def revision_to_hash(self, repo_dir, revision):
        '''Convert a revision (which may be a symbolic name, hash, etc) to a hash
        '''
        _,stdout,_ = self.hg(repo_dir, ['log', '-r', revision, '--template', "{node}"],
                      get_stdout=True)
        return stdout

    def repo_has_revision(self, repo_dir, revision):
        # don't want to print error output if revision doesn't exist
        exitcode,_,_ = self.hg(repo_dir, ['id', '-r', revision], check_return=False,
                               get_stdout=True, get_stderr=True)
        return exitcode == 0

    def is_branch_name(self, repo_dir, revision):
        _,stdout,_ = self.hg(repo_dir, ['branches', '--active'], get_stdout=True)
        for line in stdout.split('\n'):
            if line and revision == line.split()[0]:
                return True
        return False

    def repo_clone(self, repo_dir, repo_url, to_cache):
        self.hg(None, ['clone', '--noupdate', repo_url, repo_dir], quiet=False)

    def repo_pull(self, repo_dir, repo_url):
        self.hg(repo_dir, ['pull', repo_url], quiet=False)

    def repo_update(self, repo_dir, revision):
        self.hg(repo_dir, ['update', revision], quiet=False)



class HgClonerFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return HgCloner
