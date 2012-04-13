# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import base_event, forgiving_config_parser, task


class TimedEvent(base_event.BaseEvent):
    """Base class for events that trigger based on time/day.

    @var _SECTION_SUFFIX: suffix of config file sections that apply to derived
                          classes of TimedEvent.
    """

    _SECTION_SUFFIX = '_params'


    def __init__(self, keyword, deadline):
        super(TimedEvent, self).__init__(keyword)
        self._deadline = deadline


    def __ne__(self, other):
        return self._deadline != other._deadline or self.tasks != other.tasks


    def __eq__(self, other):
        return self._deadline == other._deadline and self.tasks == other.tasks


    @staticmethod
    def section_name(keyword):
        """Generate a section name for a TimedEvent config stanza."""
        return keyword + TimedEvent._SECTION_SUFFIX


    @staticmethod
    def _now():
        return datetime.datetime.now()


    @staticmethod
    def HonorsSection(section):
        """Returns True if section is something _ParseConfig() might consume."""
        return section.endswith(TimedEvent._SECTION_SUFFIX)


    def ShouldHandle(self):
        """Return True if self._deadline has passed; False if not."""
        return self._now() >= self._deadline


    def _LatestPerBranchBuildsSince(self, board, days_ago, manifest_versions):
        """Get latest per-branch, per-board builds from last |days_ago| days.

        @param board: the board whose builds we want.
        @param days_ago: how many days back to look for manifests.
        @param manifest_versions: ManifestVersions instance to use for querying.
        @return {branch: build-name}
        """
        all_branch_manifests = manifest_versions.ManifestsSince(days_ago, board)
        latest_branch_builds = {}
        for (type, milestone), manifests in all_branch_manifests.iteritems():
            build = base_event.BuildName(board, type, milestone, manifests[-1])
            latest_branch_builds[task.PickBranchName(type, milestone)] = build
        return latest_branch_builds


class Nightly(TimedEvent):
    """A TimedEvent that happens every night.

    @var KEYWORD: the keyword to use in a run_on option to associate a task
                  with the Nightly event.
    @var _DEFAULT_HOUR: can be overridden in the "nightly_params" config section
    """

    KEYWORD = 'nightly'
    _DEFAULT_HOUR = 21


    @classmethod
    def _ParseConfig(cls, config):
        section = cls.section_name(cls.KEYWORD)
        event_time = config.getint(section, 'hour') or cls._DEFAULT_HOUR
        return {'event_time': event_time,
                'always_handle': config.getboolean(section, 'always')}


    def __init__(self, event_time, always_handle=False):
        # determine if we're past today's nightly event and set the
        # next deadline for this suite appropriately.
        now = self._now()
        tonight = datetime.datetime.combine(now, datetime.time(event_time))
        # tonight is now set to today at event_time:00:00
        if tonight >= now:
            deadline = tonight
        else:
            deadline = tonight + datetime.timedelta(days=1)
        super(Nightly, self).__init__(self.KEYWORD, deadline)
        if always_handle:
            self.ShouldHandle = lambda: True


    def GetBranchBuildsForBoard(self, board, manifest_versions):
        return self._LatestPerBranchBuildsSince(board, 1, manifest_versions)


class Weekly(TimedEvent):
    """A TimedEvent that happens every week.

    @var KEYWORD: the keyword to use in a run_on option to associate a task
                  with the Weekly event.
    @var _DEFAULT_DAY: can be overridden in the "weekly_params" config section.
    @var _DEFAULT_HOUR: can be overridden in the "weekly_params" config section.
    """

    KEYWORD = 'weekly'
    _DEFAULT_DAY = 5  # Saturday
    _DEFAULT_HOUR = 23


    @classmethod
    def _ParseConfig(cls, config):
        section = cls.section_name(cls.KEYWORD)
        event_time = config.getint(section, 'hour') or cls._DEFAULT_HOUR
        event_day = config.getint(section, 'day') or cls._DEFAULT_DAY
        return {'event_time': event_time, 'event_day': event_day,
                'always_handle': config.getboolean(section, 'always')}


    def __init__(self, event_day, event_time, always_handle=False):
        # determine if we're past this week's event and set the
        # next deadline for this suite appropriately.
        now = self._now()
        # Get a datetime representing this week's event_day
        # If now() is a Sunday, we 'add' 5 - 6 = -1 days to go back a day.
        # If now() is a Monday, we add 5 - 0 = 5 days to jump forward.
        this_week = now + datetime.timedelta(event_day-now.weekday())
        this_week_deadline = datetime.datetime.combine(
            this_week, datetime.time(event_time))
        if this_week_deadline >= now:
            deadline = this_week_deadline
        else:
            deadline = this_week_deadline + datetime.timedelta(days=7)
        super(Weekly, self).__init__(self.KEYWORD, deadline)
        if always_handle:
            self.ShouldHandle = lambda: True


    def GetBranchBuildsForBoard(self, board, manifest_versions):
        return self._LatestPerBranchBuildsSince(board, 7, manifest_versions)
