# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import deduping_scheduler
import logging


class Task(object):
    """Represents an entry from the scheduler config.  Can schedule itself.

    Each entry from the scheduler config file maps one-to-one to a
    Task.  Each instance has enough info to schedule itself
    on-demand with the AFE.

    This class also overrides __hash__() and all comparitor methods to enable
    correct use in dicts, sets, etc.
    """


    def __init__(self, suite, build, pool=None):
        """Constructor

        @param suite: the name of the suite to run, e.g. 'bvt'
        @param build: the build to install e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param pool: the pool of machines to use for scheduling purposes.
                     Default: None
        """
        self._suite = suite
        self._build = build
        self._pool = pool
        # Since we expect __hash__() and other comparitor methods to be used
        # frequently by set operations, and they use str() a lot, pre-compute
        # the string representation of this object.
        self._str = '%s: %s on %s with pool %s' % (self.__class__.__name__,
                                                   suite, build, pool)


    @property
    def suite(self):
        return self._suite


    @property
    def build(self):
        return self._build


    @property
    def pool(self):
        return self._pool


    def __str__(self):
        return self._str


    def __lt__(self, other):
        return str(self) < str(other)


    def __le__(self, other):
        return str(self) <= str(other)


    def __eq__(self, other):
        return str(self) == str(other)


    def __ne__(self, other):
        return str(self) != str(other)


    def __gt__(self, other):
        return str(self) > str(other)


    def __ge__(self, other):
        return str(self) >= str(other)


    def __hash__(self):
        """Allows instances to be correctly deduped when used in a set."""
        return hash(str(self))


    def Run(self, scheduler, boards, force=False):
        """Run this task.  Returns False if it should be destroyed.

        Execute this task.  Attempt to schedule the associated suite.
        Return True if this task should be kept around, False if it
        should be destroyed.  This allows for one-shot Tasks.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param boards: the boards against which to run self._suite.
        @param force: Always schedule the suite.
        @return True if the task should be kept, False if not
        """
        for board in boards:
            try:
                if not scheduler.ScheduleSuite(self._suite, board, self._build,
                                               self._pool, force):
                    logging.info('Skipping scheduling %s for board %s',
                                 self, board)
            except deduping_scheduler.DedupingSchedulerException as e:
                logging.error(e)
        return True


class OneShotTask(Task):
    """A Task that can be run only once.  Can schedule itself."""


    def Run(self, scheduler, boards, force=False):
        """Run this task.  Returns False, indicating it should be destroyed.

        Run this task.  Attempt to schedule the associated suite.
        Return False, indicating to the caller that it should discard this task.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param boards: the boards against which to run self._suite.
        @param force: Always schedule the suite.
        @return False
        """
        super(OneShotTask, self).Run(scheduler, boards, force)
        return False
