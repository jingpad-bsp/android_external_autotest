# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import task

"""Module containing base class and methods for working with scheduler events.

@var _SECTION_SUFFIX: suffix of config file sections that apply to derived
                      classes of TimedEvent.
"""


_SECTION_SUFFIX = '_params'


class ParseBuildNameException(Exception):
    """Raised when ParseBuildName() cannot parse a build name."""
    pass


def SectionName(keyword):
    """Generate a section name for a *Event config stanza."""
    return keyword + _SECTION_SUFFIX


def HonoredSection(section):
    """Returns True if section is something _ParseConfig() might consume."""
    return section.endswith(_SECTION_SUFFIX)


def ParseBuildName(name):
    """Format a build name, given board, type, milestone, and manifest num.

    @param name: a build name, e.g. 'x86-alex-release/R20-2015.0.0'
    @return board: board the manifest is for, e.g. x86-alex.
    @return type: one of 'release', 'factory', or 'firmware'
    @return milestone: (numeric) milestone the manifest was associated with.
    @return manifest: manifest number, e.g. '2015.0.0'
    """
    match = re.match(r'([\w-]+)-(\w+)/R(\d+)-([\d.ab-]+)', name)
    if match and len(match.groups()) == 4:
        return match.groups()
    raise ParseBuildNameException('%s is a malformed build name.' % name)


def BuildName(board, type, milestone, manifest):
    """Format a build name, given board, type, milestone, and manifest number.

    @param board: board the manifest is for, e.g. x86-alex.
    @param type: one of 'release', 'factory', or 'firmware'
    @param milestone: (numeric) milestone the manifest was associated with.
    @param manifest: manifest number, e.g. '2015.0.0'
    @return a build name, e.g. 'x86-alex-release/R20-2015.0.0'
    """
    return '%s-%s/R%s-%s' % (board, type, milestone, manifest)


class BaseEvent(object):
    """Represents a supported scheduler event.

    @var _keyword: the keyword/name of this event, e.g. new_build, nightly.
    @var _mv: ManifestVersions instance used to query for new builds, etc.
    @var _tasks: set of Task instances that run on this event.
                 Use a set so that instances that encode logically equivalent
                 Tasks get de-duped before we even try to schedule them.
    """


    @classmethod
    def CreateFromConfig(cls, config, manifest_versions):
        """Instantiate a cls object, options from |config|."""
        return cls(manifest_versions, **cls._ParseConfig(config))


    @classmethod
    def _ParseConfig(cls, config):
        """Parse config and return a dict of parameters for this event.

        Uses cls.KEYWORD to determine which section to look at, and parses
        the following options:
          always_handle: If True, ShouldHandle() must always return True.

        @param config: a ForgivingConfigParser instance.
        """
        section = SectionName(cls.KEYWORD)
        return {'always_handle': config.getboolean(section, 'always_handle')}


    def __init__(self, keyword, manifest_versions, always_handle):
        """Constructor.

        @param keyword: the keyword/name of this event, e.g. nightly.
        @param manifest_versions: ManifestVersions instance to use for querying.
        @param always_handle: If True, make ShouldHandle() always return True.
        """
        self._keyword = keyword
        self._mv = manifest_versions
        self._tasks = set()
        if always_handle:
            self.ShouldHandle = lambda: True


    @property
    def keyword(self):
        """Getter for private |self._keyword| property."""
        return self._keyword


    @property
    def tasks(self):
        return self._tasks


    @tasks.setter
    def tasks(self, iterable_of_tasks):
        """Set the tasks property with an iterable.

        @param iterable_of_tasks: list of Task instances that can fire on this.
        """
        self._tasks = set(iterable_of_tasks)


    def Prepare(self):
        """Perform any one-time setup that must occur before [Should]Handle().

        Must be implemented by subclasses.
        """
        raise NotImplementedError()


    def GetBranchBuildsForBoard(self, board):
        """Get per-branch, per-board builds since last run of this event.

        @param board: the board whose builds we want.
        @return {branch: [build-name]}

        Must be implemented by subclasses.
        """
        raise NotImplementedError()


    def ShouldHandle(self):
        """Returns True if this BaseEvent should be Handle()'d, False if not.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()


    def UpdateCriteria(self):
        """Updates internal state used to decide if this event ShouldHandle()

        Must be implemented by subclasses.
        """
        raise NotImplementedError()


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
        # we need to iterate over an immutable copy of self._tasks
        for task in list(self.tasks):
            if not task.Run(scheduler, branch_builds, board, force):
                self._tasks.remove(task)
        self.UpdateCriteria()
