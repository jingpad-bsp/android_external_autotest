# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, re, os
import task
from autotest_lib.client.common_lib import autotemp, utils
from distutils import version


class ManifestVersionsException(Exception):
    """Base class for exceptions from this package."""
    pass


class QueryException(ManifestVersionsException):
    """Raised to indicate a failure while searching for manifests."""
    pass


class ManifestVersions(object):
    """Class to allow discovery of manifests for new successful CrOS builds.

    @var _MANIFEST_VERSIONS_URL: URL of the internal manifest-versions git repo.
    @var _BOARD_MANIFEST_GLOB_PATTERN: pattern for shell glob for passed-build
                                       manifests for a given board.
    @var _BOARD_MANIFEST_RE_PATTERN: pattern for regex that parses paths to
                                     manifests for a given board.

    @var _git: absolute path of git binary.
    @var _tempdir: a scoped tempdir.  Will be destroyed on instance deletion.
    """

    _MANIFEST_VERSIONS_URL = ('ssh://gerrit-int.chromium.org:29419/'
                              'chromeos/manifest-versions.git')
    _ANY_MANIFEST_GLOB_PATTERN = 'build-name/*/pass/'
    _BOARD_MANIFEST_GLOB_PATTERN = 'build-name/%s-*/pass/'
    _BOARD_MANIFEST_RE_PATTERN = (r'build-name/%s-([^-]+)(?:-group)?/pass/'
                                  '(\d+)/([0-9.]+)\.xml')


    def __init__(self):
        self._git = utils.system_output('which git')
        self._tempdir = autotemp.tempdir(unique_id='_suite_scheduler')


    def AnyManifestsSinceRev(self, revision):
      """Determine if any builds passed since git |revision|.

      @param revision: the git revision to look back to.
      @return True if any builds have passed; False otherwise.
      """
      manifest_paths = self._ExpandGlobMinusPrefix(
          self._tempdir.name, self._ANY_MANIFEST_GLOB_PATTERN)
      logging.debug('Checking if any manifests landed since %s', revision)
      log_cmd = self._BuildCommand('log',
                                   revision + '..HEAD',
                                   '--pretty="format:%H"',
                                   '--',
                                   ' '.join(manifest_paths))
      return utils.system_output(log_cmd).strip() != ''


    def Initialize(self):
        """Set up internal state.  Must be called before other methods.

        Clone manifest-versions.git into tempdir managed by this instace.
        """
        logging.debug('Cloning manifest-versions.git.')
        self._Clone()
        logging.debug('manifest-versions.git cloned.')


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
            type, milestone, manifest = matcher.match(manifest_path).groups()
            branch_manifests.setdefault((type, milestone), []).append(manifest)
        for manifest_list in branch_manifests.itervalues():
            manifest_list.sort(key=version.LooseVersion)
        return branch_manifests


    def GetCheckpoint(self):
        """Return the latest checked-out git revision in manifest-versions.git.

        @return the git hash of the latest git revision.
        """
        return utils.system_output(self._BuildCommand('log',
                                                      '--pretty="format:%H"',
                                                      '--max-count=1')).strip()


    def Update(self):
        """Get latest manifest information."""
        return utils.system(self._BuildCommand('pull'))


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
        utils.system('%s clone %s %s' % (self._git,
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
            if not utils.system_output(log_cmd):
                return []
            manifests = utils.system_output('%s|xargs %s' % (log_cmd,
                                                             self._ShowCmd()))
        except (IOError, OSError) as e:
            raise QueryException(e)
        logging.debug('found %s', manifests)
        return [m for m in re.split('\s+', manifests) if m]
