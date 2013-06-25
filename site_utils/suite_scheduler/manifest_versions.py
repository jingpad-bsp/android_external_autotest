# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import re
import time
from distutils import version

import common
from autotest_lib.client.common_lib import autotemp
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


class ManifestVersionsException(Exception):
    """Base class for exceptions from this package."""
    pass


class QueryException(ManifestVersionsException):
    """Raised to indicate a failure while searching for manifests."""
    pass


class CloneException(ManifestVersionsException):
    """Raised when `git clone` fails to create the repository."""
    pass


def _SystemOutput(command, timeout=None, args=()):
    """Shell out to run a command, expecting data on stderr. Return stdout.

    Shells out to run |command|, optionally passing escaped |args|.
    Instead of logging stderr at ERROR level, will log at default
    stdout log level.  Normal stdout is returned.

    @param command: command string to execute.
    @param timeout: time limit in seconds before attempting to kill the
            running process. The function will take a few seconds longer
            than 'timeout' to complete if it has to kill the process.
    @param args: sequence of strings of arguments to be given to the command
            inside " quotes after they have been escaped for that; each
            element in the sequence will be given as a separate command
            argument.

    @return a string with the stdout output of the command.
    """
    out = utils.run(command, timeout=timeout, ignore_status=False,
                    stderr_is_expected=True, args=args).stdout
    return out.rstrip('\n')


def _System(command, timeout=None):
    """Run a command, expecting data on stderr.

    @param command: command string to execute.
    @param timeout: timeout in seconds
    """
    utils.run(command, timeout=timeout, ignore_status=False,
              stdout_tee=utils.TEE_TO_LOGS, stderr_tee=utils.TEE_TO_LOGS,
              stderr_is_expected=True)


class ManifestVersions(object):
    """Class to allow discovery of manifests for new successful CrOS builds.

    @var _CLONE_RETRY_SECONDS: Number of seconds to wait before retrying
                                a failed `git clone` operation.
    @var _CLONE_MAX_RETRIES: Maximum number of times to retry a failed
                             a failed `git clone` operation.
    @var _MANIFEST_VERSIONS_URL: URL of the internal manifest-versions git repo.
    @var _BOARD_MANIFEST_GLOB_PATTERN: pattern for shell glob for passed-build
                                       manifests for a given board.
    @var _BOARD_MANIFEST_RE_PATTERN: pattern for regex that parses paths to
                                     manifests for a given board.

    @var _git: absolute path of git binary.
    @var _tempdir: a scoped tempdir.  Will be destroyed on instance deletion.
    """

    _CLONE_RETRY_SECONDS = 5 * 60
    _CLONE_MAX_RETRIES = 60 * 60 / _CLONE_RETRY_SECONDS
    _MANIFEST_VERSIONS_URL = ('ssh://gerrit-int.chromium.org:29419/'
                              'chromeos/manifest-versions.git')
    _ANY_MANIFEST_GLOB_PATTERN = 'build-name/*/pass/'
    _BOARD_MANIFEST_GLOB_PATTERN = 'build-name/%s-*/pass/'
    _BOARD_MANIFEST_RE_PATTERN = (r'build-name/%s-([^-]+)'
                                  r'(?:-group)?/pass/(\d+)/([0-9.]+)\.xml')


    def __init__(self):
        self._git = _SystemOutput('which git')
        self._tempdir = autotemp.tempdir(unique_id='_suite_scheduler')


    def AnyManifestsSinceRev(self, revision):
      """Determine if any builds passed since git |revision|.

      @param revision: the git revision to look back to.
      @return True if any builds have passed; False otherwise.
      """
      manifest_paths = self._ExpandGlobMinusPrefix(
          self._tempdir.name, self._ANY_MANIFEST_GLOB_PATTERN)
      if not manifest_paths:
          logging.error('No paths to check for manifests???')
          return False
      logging.info('Checking if any manifests landed since %s', revision)
      log_cmd = self._BuildCommand('log',
                                   revision + '..HEAD',
                                   '--pretty="format:%H"',
                                   '--',
                                   ' '.join(manifest_paths))
      return _SystemOutput(log_cmd).strip() != ''


    def Initialize(self):
        """Set up internal state.  Must be called before other methods.

        Clone manifest-versions.git into tempdir managed by this instance.
        """
        # If gerrit goes down during suite_scheduler operation,
        # we'll enter a loop like the following:
        #  1. suite_scheduler fails executing some `git` command.
        #  2. The failure is logged at ERROR level, causing an
        #     e-mail notification of the failure.
        #  3. suite_scheduler terminates.
        #  4. Upstart respawns suite_scheduler.
        #  5. suite_scheduler comes here to restart with a new
        #     manifest-versions repo.
        #  6. `git clone` fails, and we go back to step 2.
        #
        # We want to rate limit the e-mail notifications, so we
        # retry failed `git clone` operations for a time before we
        # finally give up.
        retry_count = 0
        msg = None
        while retry_count <= self._CLONE_MAX_RETRIES:
            if retry_count:
                time.sleep(self._CLONE_RETRY_SECONDS)
            retry_count += 1
            try:
                logging.debug('Cloning manifest-versions.git,'
                              ' attempt %d.', retry_count)
                self._Clone()
                logging.debug('manifest-versions.git cloned.')
                return
            except error.CmdError as e:
                msg = str(e)
                logging.debug('Clone failed: %s', msg)
        raise CloneException('Failed to clone %s after %d attempts: %s' %
                             (self._MANIFEST_VERSIONS_URL, retry_count, msg))


    def ManifestsSinceDays(self, days_ago, board):
        """Return map of branch:manifests for |board| for last |days_ago| days.

        To fully specify a 'branch', one needs both the type and the numeric
        milestone the branch was cut for, e.g. ('release', '19') or
        ('factory', '17').

        @param days_ago: return all manifest files from today back to |days_ago|
                         days ago.
        @param board: the board whose manifests we want to check for.
        @return {(branch_type, milestone): [manifests, oldest, to, newest]}
        """
        return self._GetManifests(
            re.compile(self._BOARD_MANIFEST_RE_PATTERN % board),
            self._QueryManifestsSinceDays(days_ago, board))


    def ManifestsSinceRev(self, rev, board):
        """Return map of branch:manifests for |board| since git |rev|.

        To fully specify a 'branch', one needs both the type and the numeric
        milestone the branch was cut for, e.g. ('release', '19') or
        ('factory', '17').

        @param rev: return all manifest files from |rev| up to HEAD.
        @param board: the board whose manifests we want to check for.
        @return {(branch_type, milestone): [manifests, oldest, to, newest]}
        """
        return self._GetManifests(
            re.compile(self._BOARD_MANIFEST_RE_PATTERN % board),
            self._QueryManifestsSinceRev(rev, board))


    def _GetManifests(self, matcher, manifest_paths):
        """Parse a list of manifest_paths into a map of branch:manifests.

        Given a regexp |matcher| and a list of paths to manifest files,
        parse the paths and build up a map of branches to manifests of
        builds on those branches.

        To fully specify a 'branch', one needs both the type and the numeric
        milestone the branch was cut for, e.g. ('release', '19') or
        ('factory', '17').

        @param matcher: a compiled regexp that can be used to parse info
                        out of the path to a manifest file.
        @param manifest_paths: an iterable of paths to manifest files.
        @return {(branch_type, milestone): [manifests, oldest, to, newest]}
        """
        branch_manifests = {}
        for manifest_path in manifest_paths:
            logging.debug('parsing manifest path %s', manifest_path)
            match = matcher.match(manifest_path)
            if not match:
                logging.info('Failed to parse path %s', manifest_path)
                continue
            groups = match.groups()
            config_type, milestone, manifest = groups
            branch = branch_manifests.setdefault((config_type, milestone), [])
            branch.append(manifest)
        for manifest_list in branch_manifests.itervalues():
            manifest_list.sort(key=version.LooseVersion)
        return branch_manifests


    def GetCheckpoint(self):
        """Return the latest checked-out git revision in manifest-versions.git.

        @return the git hash of the latest git revision.
        """
        return _SystemOutput(self._BuildCommand('log',
                                                '--pretty="format:%H"',
                                                '--max-count=1')).strip()


    def Update(self):
        """Get latest manifest information."""
        return _System(self._BuildCommand('pull'))


    def _BuildCommand(self, command, *args):
        """Build a git CLI |command|, passing space-delineated |args|.

        @param command: the git sub-command to use.
        @param args: args for the git sub-command.  Will be space-delineated.
        @return a string with the above formatted into it.
        """
        return '%s --git-dir=%s --work-tree=%s %s %s' % (
            self._git, os.path.join(self._tempdir.name, '.git'),
            self._tempdir.name, command, ' '.join(args))


    def _Clone(self):
        """Clone self._MANIFEST_VERSIONS_URL into a local temp dir."""
        # Can't use --depth here because the internal gerrit server doesn't
        # support it.  Wish we could.  http://crosbug.com/29047
        # Also, note that --work-tree and --git-dir interact oddly with
        # 'git clone', so we don't use them.
        _System('%s clone %s %s' % (self._git,
                                    self._MANIFEST_VERSIONS_URL,
                                    self._tempdir.name))


    def _ShowCmd(self):
        """Return a git command that shows file names added by commits."""
        return self._BuildCommand('show',
                                  '--pretty="format:"',
                                  '--name-only',
                                  '--diff-filter=A')


    def _QueryManifestsSinceRev(self, git_rev, board):
        """Get manifest filenames for |board|, since |git_rev|.

        @param git_rev: check for manifests newer than this git commit.
        @param board: the board whose manifests we want to check for.
        @return whitespace-delineated
        @raise QueryException if errors occur.
        """
        return self._QueryManifestsSince(git_rev + '..HEAD', board)


    def _QueryManifestsSinceDays(self, days_ago, board):
        """Return list of manifest files for |board| for last |days_ago| days.

        @param days_ago: return all manifest files from today back to |days_ago|
                         days ago.
        @param board: the board whose manifests we want to check for.
        @raise QueryException if errors occur.
        """
        return self._QueryManifestsSince('--since="%d days ago"' % days_ago,
                                         board)


    def _ExpandGlobMinusPrefix(self, prefix, path_glob):
        """Expand |path_glob| under dir |prefix|, then remove |prefix|.

        Path-concatenate prefix and path_glob, then expand the resulting glob.
        Take the results and remove |prefix| (and path separator) from each.
        Return the resulting list.

        Assuming /tmp/foo/baz and /tmp/bar/baz both exist,
        _ExpandGlobMinusPrefix('/tmp', '*/baz')  # ['bar/baz', 'foo/baz']

        @param prefix: a path under which to expand |path_glob|.
        @param path_glob: the glob to expand.
        @return a list of paths relative to |prefix|, based on |path_glob|.
        """
        full_glob = os.path.join(prefix, path_glob)
        return [p[len(prefix)+1:] for p in glob.iglob(full_glob)]


    def _QueryManifestsSince(self, since_spec, board):
        """Return list of manifest files for |board|, since |since_spec|.

        @param since_spec: a formatted arg to git log that specifies a starting
                           point to list commits from, e.g.
                             '--since="2 days ago"' or 'd34db33f..'
        @param board: the board whose manifests we want to check for.
        @raise QueryException if git log or git show errors occur.
        """
        manifest_paths = self._ExpandGlobMinusPrefix(
            self._tempdir.name, self._BOARD_MANIFEST_GLOB_PATTERN % board)
        log_cmd = self._BuildCommand('log',
                                     since_spec,
                                     '--pretty="format:%H"',
                                     '--',
                                     ' '.join(manifest_paths))
        try:
            # If we pass nothing to git show, we get unexpected results.
            # So, return early if git log is going to give us nothing.
            if not manifest_paths or not _SystemOutput(log_cmd):
                return []
            manifests = _SystemOutput('%s|xargs %s' % (log_cmd,
                                                       self._ShowCmd()))
        except (IOError, OSError) as e:
            raise QueryException(e)
        logging.debug('found %s', manifests)
        return [m for m in re.split('\s+', manifests) if m]
