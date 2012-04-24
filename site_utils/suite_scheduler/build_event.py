# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base_event, forgiving_config_parser, manifest_versions, task


class BuildEvent(base_event.BaseEvent):
    """Base class for events that come from the build system.

    For example, a new build completing or a new version of Chromium.

    @var _revision: The last git revision we checked for new build artifacts.
    """


    def __init__(self, keyword, manifest_versions, always_handle):
        """Constructor.

        @param keyword: the keyword/name of this event, e.g. nightly.
        @param manifest_versions: ManifestVersions instance to use for querying.
        @param always_handle: If True, make ShouldHandle() always return True.
        """
        super(BuildEvent, self).__init__(keyword, manifest_versions,
                                         always_handle)
        # git log HEAD..HEAD is always a no-op.
        self._revision = 'HEAD'


    def ShouldHandle(self):
        # TODO(cmasone): Check to see if there's a new build since the last hash
        return False  # For now.


    def _AllPerBranchBuildsSince(self, board, revision):
        """Get all per-branch, per-board builds since git |revision|.

        @param board: the board whose builds we want.
        @param revision: the revision to look back until.
        @return {branch: [build-name1, build-name2]}
        """
        all_branch_manifests = self._mv.ManifestsSinceRev(revision, board)
        all_branch_builds = {}
        for (type, milestone), manifests in all_branch_manifests.iteritems():
            branch_name = task.PickBranchName(type, milestone)
            for manifest in manifests:
                build = base_event.BuildName(board, type, milestone, manifest)
                all_branch_builds.setdefault(branch_name, []).append(build)
        return all_branch_builds


    def GetBranchBuildsForBoard(self, board):
        return self._AllPerBranchBuildsSince(board, self._revision)


    def Handle(self, scheduler, branch_builds, board, force=False):
        """Runs all tasks in self._tasks.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param branch_builds: a dict mapping branch name to the build to
                              install for that branch, e.g.
                              {'R18': ['x86-alex-release/R18-1655.0.0'],
                               'R19': ['x86-alex-release/R19-2077.0.0']
                               'factory': ['x86-alex-factory/R19-2077.0.5']}
        @param board: the board against which to Run() all of self._tasks.
        @param force: Tell every Task to always Run().
        """
        super(BuildEvent, self).Handle(scheduler, branch_builds, board, force)
        # Get new checkpoint, so that next time we come around, we
        # don't keep looking back to the same revision.
        self._revision = self._mv.GetCheckpoint()


class NewBuild(BuildEvent):
    KEYWORD = 'new_build'


    def __init__(self, mv, always_handle):
        """Constructor.

        @param mv: ManifestVersions instance to use for querying.
        @param always_handle: If True, make ShouldHandle() always return True.
        """
        super(NewBuild, self).__init__(self.KEYWORD, mv, always_handle)


    def UpdateCriteria(self):
        self._revision = self._mv.GetCheckpoint()
