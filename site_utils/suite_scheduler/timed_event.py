# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import base_event, forgiving_config_parser, task


class TimedEvent(base_event.BaseEvent):

    _SECTION_SUFFIX = '_params'


    @classmethod
    def CreateFromConfig(cls, config, tasks):
        """Instantiate a cls object, with |tasks| and options from |config|."""
        return cls(tasks=tasks, **cls._ParseConfig(config))


    @classmethod
    def _ParseConfig(cls, config):
        """Parse config and return a dict of parameters."""
        raise NotImplementedError()


    def __init__(self, keyword, deadline, tasks):
        super(TimedEvent, self).__init__(keyword, tasks)
        self._deadline = deadline


    def __ne__(self, other):
        return self._deadline != other._deadline or self._tasks != other._tasks


    def __eq__(self, other):
        return self._deadline == other._deadline and self._tasks == other._tasks


    @staticmethod
    def section_name(keyword):
        """Generate a section name for a TimedEvent config stanza."""
        return keyword + TimedEvent._SECTION_SUFFIX


    @staticmethod
    def _now():
        return datetime.datetime.now()


    def ShouldHandle(self):
        """Return True if self._deadline has passed; False if not."""
        return self._now() >= self._deadline


class Nightly(TimedEvent):


    KEYWORD = 'nightly'
    _DEFAULT_HOUR = 21


    @classmethod
    def _ParseConfig(cls, config):
        section = cls.section_name(cls.KEYWORD)
        event_time = config.getint(section, 'hour') or cls._DEFAULT_HOUR
        return {'event_time': event_time}


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
        super(Nightly, self).__init__(self.KEYWORD, deadline, tasks)


class Weekly(TimedEvent):


    KEYWORD = 'weekly'
    _DEFAULT_DAY = 5  # Saturday
    _DEFAULT_HOUR = 23


    @classmethod
    def _ParseConfig(cls, config):
        section = cls.section_name(cls.KEYWORD)
        event_time = config.getint(section, 'hour') or cls._DEFAULT_HOUR
        event_day = config.getint(section, 'day') or cls._DEFAULT_DAY
        return {'event_time': event_time, 'event_day': event_day}


    def __init__(self, event_day, event_time, tasks):
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
        super(Weekly, self).__init__(self.KEYWORD, deadline, tasks)
