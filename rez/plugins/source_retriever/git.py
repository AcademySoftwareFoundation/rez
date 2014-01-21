from rez import plugin_factory
from rez.source_retrieval import RepoCloner
import os
import os.path



class GitCloner(RepoCloner):
    @classmethod
    def name(cls):
        return "git"

    @classmethod
    def supported_url_types(cls):
        return ['.git']

    @classmethod
    def repo_current_symbol(cls, repo_dir):
        '''Returns the symbol that represents the "current" revision
        '''
        return "HEAD"

    def git(self, repo_dir, git_args, bare=None, get_stdout=False, get_stderr=False,
            check_return=True, quiet=True, **subprocess_kwargs):
        '''Run a git command for the given repo_dir, with the given args

        Parameters
        ----------
        repo_dir : basestring or None
            if non-None, a git working dir to set as the repo to use; note that
            since this is a required argument, if you wish to run a git command
            that does not need a current repository (ie,
            'git --version', 'hg clone', etc), you must explicitly pass None
        git_args : strings
            args to pass to git (as on the command line)
        bare : bool or None
            whether or not the repo_dir is a "bare" git repo (ie, if this is
            false, <repo_dir>/.git should exist); if None, then will attempt
            to auto-determine whether the repo is bare (by checking for a
            <repo_dir>/.git dir)
        '''
        args = ['git']
        if repo_dir is not None:
            if bare is None:
                bare = not os.path.exists(os.path.join(repo_dir, '.git'))
            if bare:
                args.extend(['--git-dir', repo_dir])
            else:
                args.extend(['--work-tree', repo_dir, '--git-dir',
                             os.path.join(repo_dir, '.git')])
        args.extend(git_args)
        return self._subprocess(args,
                                get_stdout=get_stdout,
                                get_stderr=get_stderr,
                                check_return=check_return,
                                quiet=quiet,
                                **subprocess_kwargs)

    def _current_branch(self, repo_dir):
        _,stdout,_ = self.git(repo_dir, ['rev-parse', '--abbrev-ref', 'HEAD'], get_stdout=True)
        return stdout

    def _repo_remote_for_url(self, repo_dir, repo_url):
        '''Given a remote repo url, returns the remote name that has that url
        as it's fetch url (creating / setting the rez_remote remote, if none
        exists)
        '''
        _,stdout,_ = self.git(repo_dir, ['remote', '-v'], get_stdout=True)

        # for comparison, we need to "standardize" the repo url, by removing
        # any multiple whitespace (though there probably shouldn't be
        # whitespace)
        repo_url = ' '.join(repo_url.strip().split())
        default_remote = 'rez_remote'
        found_default = False

        for line in stdout.split('\n'):
            # line we want looks like:
            # origin  git@github.com:SomeGuy/myrepo.git (fetch)
            fetch_str = ' (fetch)'
            line = line.strip()
            if not line.endswith(fetch_str):
                continue
            split_line = line[:-len(fetch_str)].split()
            if len(split_line) < 2:
                continue
            remote_name = split_line[0]
            if remote_name == default_remote:
                found_default = True
            remote_url = ' '.join(split_line[1:])
            if remote_url == repo_url:
                return remote_name

        # if we've gotten here, we didn't find an existing remote that had
        # the desired url...
        if not found_default:
            # make one...
            self.git(repo_dir, ['remote', 'add', default_remote, repo_url])
        else:
            # ...or update existing...
            self.git(repo_dir, ['remote', 'set-url', default_remote, repo_url])
        return default_remote

    def revision_to_hash(self, repo_dir, revision):
        '''Convert a revision (which may be a symbolic name, hash, etc) to a
        hash
        '''
        branch = self._find_branch(repo_dir, revision)
        if branch:
            revision = branch
        _,stdout,_ = self.git(repo_dir, ['rev-parse', revision], get_stdout=True)
        return stdout

    def _iter_branches(self, repo_dir, remote=True, local=True):
        _,stdout,_ = self.git(repo_dir, ['branch', '-a'], get_stdout=True)
        for line in stdout.split('\n'):
            toks = line.strip('* ').split()
            if toks:
                branch = None
                alias = None

                if remote and toks[0].startswith('remotes/'):
                    if '->' in toks:
                        alias = toks[0]
                        branch = 'remotes/' + toks[2]
                    else:
                        branch = toks[0]
                    yield branch,alias
                elif local and not toks[0].startswith('remotes/'):
                    if '->' in toks:
                        alias = toks[0]
                        branch = toks[2]
                    else:
                        branch = toks[0]
                    yield branch,alias

    def _find_branch(self, repo_dir, name, remote=True, local=True):
        for branch,_ in self._iter_branches(repo_dir, remote, local):
            if branch.split('/')[-1] == name:
                return branch

    def is_branch_name(self, repo_dir, revision):
        return bool(self._find_branch(repo_dir, revision))

    def repo_has_revision(self, repo_dir, revision):
        exitcode,_,_ = self.git(repo_dir, ['cat-file', '-e', revision],
                           check_return=False)
        return exitcode == 0

    def repo_clone(self, repo_dir, repo_url, to_cache):
        # -n makes it not do a checkout
        args = ['clone', '-n']
        if to_cache:
            # use mirror so we get all the branches as well, with a direct
            # mirror default fetch for branches.
            # mirror implies bare.
            args.append('--mirror')
        args.extend([repo_url, repo_dir])
        self.git(None, args, quiet=False)

    def repo_pull(self, repo_dir, repo_url):
        remote_name = self._repo_remote_for_url(repo_dir, repo_url)
        self.git(repo_dir, ['fetch', remote_name], quiet=False)

    def repo_update(self, repo_dir, revision):
        curr_branch = self._current_branch(repo_dir)
        branch = self._find_branch(repo_dir, revision)

        if branch and branch.startswith('remotes/'):
            print "creating tracking branch for", revision
            self.git(repo_dir, ['checkout', '--track', 'origin/' + revision], quiet=False)
        else:
            # need to use different methods to update, depending on whether or
            # not we're switching branches...
            # AJ why the Rez local branch??
            if curr_branch == 'rez':
                # if branch is already rez, need to use "reset"
                self.git(repo_dir, ['reset', '--hard', revision], quiet=False)
            else:
                # create / checkout a branch called "rez"
                self.git(repo_dir, ['checkout', '-B', 'rez', revision], quiet=False)



class GitClonerFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return GitCloner
