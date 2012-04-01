# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import task


class BaseEvent(object):
    """Represents a supported scheduler event.

    @var _keyword: the keyword/name of this event, e.g. new_build, nightly.
    @var _tasks: set of Task instances that run on this event.
                 Use a set so that instances that encode logically equivalent
                 Tasks get de-duped before we even try to schedule them.
    """


    def __init__(self, keyword, tasks):
        """Constructor.

        @param keyword: the keyword/name of this event, e.g. nightly.
        @param tasks: list of Task instances that can fire on this.
        """
        self._keyword = keyword
        self._tasks = set(tasks)


    @property
    def keyword(self):
        """Getter for private |self._keyword| property."""
        return self._keyword


    def ShouldFire(self):
        """Returns True if this BaseEvent should be fired, False if not.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()


    def Fire(self, scheduler, force=False):
        """Runs all tasks in self._tasks.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param force: Tell every job to always trigger.
        """
        # we need to iterate over an immutable copy of self._tasks
        for job in list(self._tasks):
            if not job.Run(scheduler, force):
                self._tasks.remove(job)


class TimedEvent(BaseEvent):


    def __init__(self, keyword, deadline, tasks):
        super(TimedEvent, self).__init__(keyword, tasks)
        self._deadline = deadline


    @staticmethod
    def _now():
        return datetime.datetime.now()


    def ShouldFire(self):
        return self._now() >= self._deadline


class Nightly(TimedEvent):


    _EVENT_KEYWORD = 'nightly'


    def __init__(self, event_time, tasks):
        # determine if we're past today's nightly event and set the
        # next deadline for this suite appropriately.
        now = self._now()
        tonight = datetime.datetime.combine(now, datetime.time(event_time))
        # tonight is now set to today at event_time:00:00
        if tonight >= now:
            deadline = tonight
        else:
            deadline = tonight + datetime.timedelta(days=1)
        super(Nightly, self).__init__(self._EVENT_KEYWORD, deadline, tasks)


class Weekly(TimedEvent):


    _EVENT_KEYWORD = 'weekly'


    def __init__(self, event_day, event_hour, tasks):
        # determine if we're past this week's event and set the
        # next deadline for this suite appropriately.
        now = self._now()
        # Get a datetime representing this week's event_day
        # If now() is a Sunday, we 'add' 5 - 6 = -1 days to go back a day.
        # If now() is a Monday, we add 5 - 0 = 5 days to jump forward.
        this_week = now + datetime.timedelta(event_day-now.weekday())
        this_week_deadline = datetime.datetime.combine(
            this_week, datetime.time(event_hour))
        if this_week_deadline >= now:
            deadline = this_week_deadline
        else:
            deadline = this_week_deadline + datetime.timedelta(days=7)
        super(Weekly, self).__init__(self._EVENT_KEYWORD, deadline, tasks)
