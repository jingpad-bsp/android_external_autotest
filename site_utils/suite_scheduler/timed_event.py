# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging

import common
from autotest_lib.client.common_lib import priorities

import base_event, forgiving_config_parser, task


class TimedEvent(base_event.BaseEvent):
    """Base class for events that trigger based on time/day.

    @var _deadline: If this time has passed, ShouldHandle() returns True.
    """


    def __init__(self, keyword, manifest_versions, always_handle, deadline):
        """Constructor.

        @param keyword: the keyword/name of this event, e.g. nightly.
        @param manifest_versions: ManifestVersions instance to use for querying.
        @param always_handle: If True, make ShouldHandle() always return True.
        @param deadline: This instance's initial |_deadline|.
        """
        super(TimedEvent, self).__init__(keyword, manifest_versions,
                                         always_handle)
        self._deadline = deadline


    def __ne__(self, other):
        return self._deadline != other._deadline or self.tasks != other.tasks


    def __eq__(self, other):
        return self._deadline == other._deadline and self.tasks == other.tasks


    @staticmethod
    def _now():
        return datetime.datetime.now()


    def Prepare(self):
        pass


    def ShouldHandle(self):
        """Return True if self._deadline has passed; False if not."""
        if super(TimedEvent, self).ShouldHandle():
            return True
        else:
            logging.info('Checking deadline %s for event %s',
                         self._deadline, self.keyword)
            return self._now() >= self._deadline


    def _LatestPerBranchBuildsSince(self, board, days_ago):
        """Get latest per-branch, per-board builds from last |days_ago| days.

        @param board: the board whose builds we want.
        @param days_ago: how many days back to look for manifests.
        @return {branch: [build-name]}
        """
        all_branch_manifests = self._mv.ManifestsSinceDays(days_ago, board)
        latest_branch_builds = {}
        for (type, milestone), manifests in all_branch_manifests.iteritems():
            build = base_event.BuildName(board, type, milestone, manifests[-1])
            latest_branch_builds[task.PickBranchName(type, milestone)] = [build]
        logging.info('%s event found candidate builds: %r',
                     self.keyword, latest_branch_builds)
        return latest_branch_builds


class Nightly(TimedEvent):
    """A TimedEvent that happens every night.

    @var KEYWORD: the keyword to use in a run_on option to associate a task
                  with the Nightly event.
    @var _DEFAULT_HOUR: can be overridden in the "nightly_params" config section
    """

    KEYWORD = 'nightly'
    _DEFAULT_HOUR = 21
    PRIORITY = priorities.Priority.DAILY
    TIMEOUT = 24  # Kicked off once a day, so they get the full day to run


    @classmethod
    def _ParseConfig(cls, config):
        """Create args to pass to __init__ by parsing |config|.

        Calls super class' _ParseConfig() method, then parses these additonal
        options:
          hour: Integer hour, on a 24 hour clock.
        """
        from_base = super(Nightly, cls)._ParseConfig(config)

        section = base_event.SectionName(cls.KEYWORD)
        event_time = config.getint(section, 'hour') or cls._DEFAULT_HOUR

        from_base.update({'event_time': event_time})
        return from_base


    def __init__(self, manifest_versions, always_handle, event_time):
        """Constructor.

        @param manifest_versions: ManifestVersions instance to use for querying.
        @param always_handle: If True, make ShouldHandle() always return True.
        @param event_time: The hour of the day to set |self._deadline| at.
        """
        # determine if we're past today's nightly event and set the
        # next deadline for this suite appropriately.
        now = self._now()
        tonight = datetime.datetime.combine(now, datetime.time(event_time))
        # tonight is now set to today at event_time:00:00
        if tonight >= now:
            deadline = tonight
        else:
            deadline = tonight + datetime.timedelta(days=1)
        super(Nightly, self).__init__(self.KEYWORD, manifest_versions,
                                      always_handle, deadline)


    def Merge(self, to_merge):
        """Merge this event with to_merge, changing some mutable properties.

        keyword remains unchanged; the following take on values from to_merge:
          _deadline iff the time of day in to_merge._deadline is different.

        @param to_merge: A TimedEvent instance to merge into this isntance.
        """
        super(Nightly, self).Merge(to_merge)
        if self._deadline.time() != to_merge._deadline.time():
            self._deadline = to_merge._deadline


    def GetBranchBuildsForBoard(self, board):
        return self._LatestPerBranchBuildsSince(board, 1)


    def UpdateCriteria(self):
        self._deadline = self._deadline + datetime.timedelta(days=1)


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
    PRIORITY = priorities.Priority.WEEKLY
    TIMEOUT = 7 * 24  # 7 days


    @classmethod
    def _ParseConfig(cls, config):
        """Create args to pass to __init__ by parsing |config|.

        Calls super class' _ParseConfig() method, then parses these additonal
        options:
          hour: Integer hour, on a 24 hour clock.
          day: Integer day, in a 0-indexed 7 day week, e.g. 5 == Saturday.
        """
        from_base = super(Weekly, cls)._ParseConfig(config)

        section = base_event.SectionName(cls.KEYWORD)
        event_time = config.getint(section, 'hour') or cls._DEFAULT_HOUR
        event_day = config.getint(section, 'day') or cls._DEFAULT_DAY

        from_base.update({'event_time': event_time, 'event_day': event_day})
        return from_base


    def __init__(self, manifest_versions, always_handle, event_day, event_time):
        """Constructor.

        @param manifest_versions: ManifestVersions instance to use for querying.
        @param always_handle: If True, make ShouldHandle() always return True.
        @param event_day: The day of the week to set |self._deadline| at.
        @param event_time: The hour of the day to set |self._deadline| at.
        """
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
        super(Weekly, self).__init__(self.KEYWORD, manifest_versions,
                                     always_handle, deadline)


    def Merge(self, to_merge):
        """Merge this event with to_merge, changing some mutable properties.

        keyword remains unchanged; the following take on values from to_merge:
          _deadline iff the time of day in to_merge._deadline is different.

        @param to_merge: A TimedEvent instance to merge into this isntance.
        """
        super(Weekly, self).Merge(to_merge)
        if (self._deadline.time() != to_merge._deadline.time() or
            self._deadline.weekday() != to_merge._deadline.weekday()):
            self._deadline = to_merge._deadline


    def GetBranchBuildsForBoard(self, board):
        return self._LatestPerBranchBuildsSince(board, 7)


    def UpdateCriteria(self):
        self._deadline = self._deadline + datetime.timedelta(days=7)
