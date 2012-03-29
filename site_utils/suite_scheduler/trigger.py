# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import triggerable_event


class BaseTrigger(object):
    """Represents a supported scheduler trigger.

    @var _keyword: the keyword/name of this trigger, e.g. new_build, nightly.
    @var _events: set of TriggerableEvent instances that fire on this trigger.
                  Use a set so that instances that encode logically equivalent
                  Events get de-duped before we even try to schedule them.
    """


    def __init__(self, keyword, events):
        """Constructor.

        @param keyword: the keyword/name of this trigger, e.g. nightly.
        @param events: list of TriggerableEvent instances that can fire on this.
        """
        self._keyword = keyword
        self._events = set(events)


    @property
    def keyword(self):
        """Getter for private |self._keyword| property."""
        return self._keyword


    def ShouldFire(self):
        """Returns True if this BaseTrigger should be fired, False if not.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()


    def Fire(self, scheduler, force=False):
        """Triggers all events in self._events.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param force: Tell every job to always trigger.
        """
        # we need to iterate over an immutable copy of self._events
        for job in list(self._events):
            if not job.Trigger(scheduler, force):
                self._events.remove(job)


class TimedTrigger(BaseTrigger):


    def __init__(self, keyword, deadline, events):
        super(TimedTrigger, self).__init__(keyword, events)
        self._deadline = deadline


    @staticmethod
    def _now():
        return datetime.datetime.now()


    def ShouldFire(self):
        return self._now() >= self._deadline


class Nightly(TimedTrigger):


    _TRIGGER_KEYWORD = 'nightly'


    def __init__(self, trigger_time, events):
        # determine if we're past today's nightly trigger and set the
        # next deadline for this suite appropriately.
        now = self._now()
        tonight = datetime.datetime.combine(now, datetime.time(trigger_time))
        # tonight is now set to today at trigger_time:00:00
        if tonight >= now:
            deadline = tonight
        else:
            deadline = tonight + datetime.timedelta(days=1)
        super(Nightly, self).__init__(self._TRIGGER_KEYWORD, deadline, events)


class Weekly(TimedTrigger):


    _TRIGGER_KEYWORD = 'weekly'


    def __init__(self, trigger_day, trigger_hour, events):
        # determine if we're past this week's trigger and set the
        # next deadline for this suite appropriately.
        now = self._now()
        # Get a datetime representing this week's trigger_day
        # If now() is a Sunday, we 'add' 5 - 6 = -1 days to go back a day.
        # If now() is a Monday, we add 5 - 0 = 5 days to jump forward.
        this_week = now + datetime.timedelta(trigger_day-now.weekday())
        this_week_deadline = datetime.datetime.combine(
            this_week, datetime.time(trigger_hour))
        if this_week_deadline >= now:
            deadline = this_week_deadline
        else:
            deadline = this_week_deadline + datetime.timedelta(days=7)
        super(Weekly, self).__init__(self._TRIGGER_KEYWORD, deadline, events)
