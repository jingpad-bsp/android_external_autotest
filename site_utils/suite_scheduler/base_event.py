# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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


    def ShouldHandle(self):
        """Returns True if this BaseEvent should be fired, False if not.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()


    def Handle(self, scheduler, boards, force=False):
        """Runs all tasks in self._tasks.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param boards: the boards against which to Run() all of self._tasks.
        @param force: Tell every job to always trigger.
        """
        # we need to iterate over an immutable copy of self._tasks
        for task in list(self._tasks):
            if not task.Run(scheduler, boards, force):
                self._tasks.remove(task)
