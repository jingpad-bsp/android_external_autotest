"""
Module with abstraction layers to revision control systems.

With this library, autotest developers can handle source code checkouts and
updates on both client as well as server code.
"""

import os, warnings, logging
import error, utils
from autotest_lib.client.bin import os_dep


class RevisionControlError(Exception):
    """Local exception to be raised by code in this file."""


class GitError(RevisionControlError):
    """Exceptions raised for general git errors."""


class GitCloneError(GitError):
    """Exceptions raised for git clone errors."""


class GitFetchError(GitError):
    """Exception raised for git fetch errors."""


class GitPullError(GitError):
    """Exception raised for git pull errors."""


class GitResetError(GitError):
    """Exception raised for git reset errors."""


class GitCommitError(GitError):
    """Exception raised for git commit errors."""


class GitRepo(object):
    """
    This class represents a git repo.

    It is used to pull down a local copy of a git repo, check if the local
    repo is up-to-date, if not update.  It delegates the install to
    implementation classes.
    """

    def __init__(self, repodir, giturl, weburl=None, abs_work_tree=None):
        """
        Initialized reposotory.

        @param repodir: destination repo directory.
        @param giturl: master repo git url.
        @param weburl: a web url for the master repo.
        @param abs_work_tree: work tree of the git repo. In the
            absence of a work tree git manipulations will occur
            in the current working directory for non bare repos.
            In such repos the -git-dir option should point to
            the .git directory and -work-tree should point to
            the repos working tree.
        Note: a bare reposotory is one which contains all the
        working files (the tree) and the other wise hidden files
        (.git) in the same directory. This class assumes non-bare
        reposotories.
        """
        if repodir is None:
            raise ValueError('You must provide a path that will hold the'
                             'git repository')
        self.repodir = utils.sh_escape(repodir)
        if giturl is None:
            raise ValueError('You must provide a git URL repository')
        self.giturl = giturl
        if weburl is not None:
            warnings.warn("Param weburl: You are no longer required to provide "
                          "a web URL for your git repos", DeprecationWarning)

        # path to .git dir
        self.gitpath = utils.sh_escape(os.path.join(self.repodir,'.git'))

        # Find git base command. If not found, this will throw an exception
        self.git_base_cmd = os_dep.command('git')
        self.git_dir = giturl
        self.work_tree = abs_work_tree

        # default to same remote path as local
        self._build = os.path.dirname(self.repodir)


    def gen_git_cmd_base(self):
        """
        The command we use to run git cannot be set. It is reconstructed
        on each access from it's component variables. This is it's getter.
        """
        # base git command , pointing to gitpath git dir
        gitcmdbase = '%s --git-dir=%s' % (self.git_base_cmd,
                                          self.gitpath)
        if self.work_tree:
            gitcmdbase += ' --work-tree=%s' % self.work_tree
        return gitcmdbase


    def _run(self, command, timeout=None, ignore_status=False):
        """
        Auxiliary function to run a command, with proper shell escaping.

        @param timeout: Timeout to run the command.
        @param ignore_status: Whether we should supress error.CmdError
                exceptions if the command did return exit code !=0 (True), or
                not supress them (False).
        """
        return utils.run(r'%s' % (utils.sh_escape(command)),
                         timeout, ignore_status)


    def gitcmd(self, cmd, ignore_status=False):
        """
        Wrapper for a git command.

        @param cmd: Git subcommand (ex 'clone').
        @param ignore_status: Whether we should supress error.CmdError
                exceptions if the command did return exit code !=0 (True), or
                not supress them (False).
        """
        cmd = '%s %s' % (self.gen_git_cmd_base(), cmd)
        return self._run(cmd, ignore_status=ignore_status)


    def clone(self):
        """
        Clones a repo using giturl and repodir.

        Since we're cloning the master repo we don't have a work tree yet,
        make sure the getter of the gitcmd doesn't think we do by setting
        work_tree to None.

        @raises GitCloneError: if cloning the master repo fails.
        """
        logging.info('Cloning git repo %s', self.giturl)
        cmd = 'clone %s %s ' % (self.giturl, self.repodir)
        abs_work_tree = self.work_tree
        self.work_tree = None
        try:
            rv = self.gitcmd(cmd, True)
            if rv.exit_status != 0:
                logging.error(rv.stderr)
                raise GitCloneError('Failed to clone git url', rv)
            else:
                logging.info(rv.stdout)
        finally:
            self.work_tree = abs_work_tree


    def pull(self, rebase=False):
        """
        Pulls into repodir using giturl.

        @param rebase: If true forces git pull to perform a rebase instead of a
                        merge.
        @raises GitPullError: if pulling from giturl fails.
        """
        logging.info('Updating git repo %s', self.giturl)
        cmd = 'pull '
        if rebase:
            cmd += '--rebase '
        cmd += self.giturl

        rv = self.gitcmd(cmd, True)
        if rv.exit_status != 0:
            logging.error(rv.stderr)
            e_msg = 'Failed to pull git repo data'
            raise GitPullError(e_msg, rv)


    def commit(self, msg='default'):
        """
        Commit changes to repo with the supplied commit msg.

        @param msg: A message that goes with the commit.
        """
        rv = self.gitcmd('commit -a -m %s' % msg)
        if rv.exit_status != 0:
            logging.error(rv.stderr)
            raise revision_control.GitCommitError('Unable to commit', rv)


    def reset_head(self):
        """
        Reset repo to HEAD@{0} by running git reset --hard HEAD.

        @raises GitResetError: if we fails to reset HEAD.
        """
        logging.info('Resetting head on repo %s', self.repodir)
        rv = self.gitcmd('reset --hard HEAD')
        if rv.exit_status != 0:
            logging.error(rv.stderr)
            e_msg = 'Failed to reset HEAD'
            raise GitResetError(e_msg, rv)


    def fetch_remote(self):
        """
        Fetches all files from the remote but doesn't reset head.

        @raises GitFetchError: if we fail to fetch all files from giturl.
        """
        logging.info('fetching from repo %s', self.giturl)
        rv = self.gitcmd('fetch --all')
        if rv.exit_status != 0:
            logging.error(rv.stderr)
            e_msg = 'Failed to fetch from %s' % self.giturl
            raise GitFetchError(e_msg, rv)


    def pull_or_clone(self):
        """
        Pulls if the repo is already initialized, clones if it isn't.
        """
        # TODO beeps: if the user has local changes in the repo they're
        # pulling into, this could fail on rebase. Currently the only consumer
        # of this method is external_packages and it makes sense for
        # build_externals to fail in such a scenario. Investigate ways to get
        # this to squash local changes using git rev-parse to get the upstream
        # tracking branch name, and then do a fetch + reset head.
        if self.is_repo_initialized():
            self.pull(rebase=True)
        else:
            self.clone()


    def get(self, **kwargs):
        """
        This method overrides baseclass get so we can do proper git
        clone/pulls, and check for updated versions.  The result of
        this method will leave an up-to-date version of git repo at
        'giturl' in 'repodir' directory to be used by build/install
        methods.

        @param **kwargs: Dictionary of parameters to the method get.
        """
        if not self.is_repo_initialized():
            # this is your first time ...
            self.clone()
        elif self.is_out_of_date():
            # exiting repo, check if we're up-to-date
            self.pull()
        else:
            logging.info('repo up-to-date')

        # remember where the source is
        self.source_material = self.repodir


    def get_local_head(self):
        """
        Get the top commit hash of the current local git branch.

        @return: Top commit hash of local git branch
        """
        cmd = 'log --pretty=format:"%H" -1'
        l_head_cmd = self.gitcmd(cmd)
        return l_head_cmd.stdout.strip()


    def get_remote_head(self):
        """
        Get the top commit hash of the current remote git branch.

        @return: Top commit hash of remote git branch
        """
        cmd1 = 'remote show'
        origin_name_cmd = self.gitcmd(cmd1)
        cmd2 = 'log --pretty=format:"%H" -1 ' + origin_name_cmd.stdout.strip()
        r_head_cmd = self.gitcmd(cmd2)
        return r_head_cmd.stdout.strip()


    def is_out_of_date(self):
        """
        Return whether this branch is out of date with regards to remote branch.

        @return: False, if the branch is outdated, True if it is current.
        """
        local_head = self.get_local_head()
        remote_head = self.get_remote_head()

        # local is out-of-date, pull
        if local_head != remote_head:
            return True

        return False


    def is_repo_initialized(self):
        """
        Return whether the git repo was already initialized.

        Counts objects in .git directory, since these will exist even if the
        repo is empty. Assumes non-bare reposotories like the rest of this file.

        @return: True if the repo is initialized.
        """
        cmd = 'count-objects'
        rv = self.gitcmd(cmd, True)
        if rv.exit_status == 0:
            return True

        return False


    def get_latest_commit_hash(self):
        """
        Get the commit hash of the latest commit in the repo.

        We don't raise an exception if no commit hash was found as
        this could be an empty repository. The caller should notice this
        methods return value and raise one appropriately.

        @return: The first commit hash if anything has been committed.
        """
        cmd = 'rev-list -n 1 --all'
        rv = self.gitcmd(cmd, True)
        if rv.exit_status == 0:
            return rv.stdout
        return None


    def is_repo_empty(self):
        """
        Checks for empty but initialized repos.

        eg: we clone an empty master repo, then don't pull
        after the master commits.

        @return True if the repo has no commits.
        """
        if self.get_latest_commit_hash():
            return False
        return True


    def get_revision(self):
        """
        Return current HEAD commit id
        """
        if not self.is_repo_initialized():
            self.get()

        cmd = 'rev-parse --verify HEAD'
        gitlog = self.gitcmd(cmd, True)
        if gitlog.exit_status != 0:
            logging.error(gitlog.stderr)
            raise error.CmdError('Failed to find git sha1 revision', gitlog)
        else:
            return gitlog.stdout.strip('\n')


    def checkout(self, remote, local=None):
        """
        Check out the git commit id, branch, or tag given by remote.

        Optional give the local branch name as local.

        @param remote: Remote commit hash
        @param local: Local commit hash
        @note: For git checkout tag git version >= 1.5.0 is required
        """
        if not self.is_repo_initialized():
            self.get()

        assert(isinstance(remote, basestring))
        if local:
            cmd = 'checkout -b %s %s' % (local, remote)
        else:
            cmd = 'checkout %s' % (remote)
        gitlog = self.gitcmd(cmd, True)
        if gitlog.exit_status != 0:
            logging.error(gitlog.stderr)
            raise error.CmdError('Failed to checkout git branch', gitlog)
        else:
            logging.info(gitlog.stdout)


    def get_branch(self, all=False, remote_tracking=False):
        """
        Show the branches.

        @param all: List both remote-tracking branches and local branches (True)
                or only the local ones (False).
        @param remote_tracking: Lists the remote-tracking branches.
        """
        if not self.is_repo_initialized():
            self.get()

        cmd = 'branch --no-color'
        if all:
            cmd = " ".join([cmd, "-a"])
        if remote_tracking:
            cmd = " ".join([cmd, "-r"])

        gitlog = self.gitcmd(cmd, True)
        if gitlog.exit_status != 0:
            logging.error(gitlog.stderr)
            raise error.CmdError('Failed to get git branch', gitlog)
        elif all or remote_tracking:
            return gitlog.stdout.strip('\n')
        else:
            branch = [b[2:] for b in gitlog.stdout.split('\n')
                      if b.startswith('*')][0]
            return branch
