# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ConfigParser, logging, time

import deduping_scheduler, timed_event, platform_enumerator


class Driver(object):
    """Implements the main loop of the suite_scheduler.

    @var _LOOP_INTERVAL: time to wait between loop iterations.

    @var _scheduler: a DedupingScheduler, used to schedule jobs with the AFE.
    @var _enumerator: a PlatformEnumerator, used to list plaforms known to
                      the AFE
    @var _events: list of BaseEvents to be handled each time through main loop.
    """

    _LOOP_INTERVAL = 5


    def __init__(self, afe, config):
        """Constructor

        @param afe: an instance of AFE as defined in server/frontend.py.
        @param config: an instance of ForgivingConfigParser.
        """
        self._scheduler = deduping_scheduler.DedupingScheduler(afe)
        self._enumerator = platform_enumerator.PlatformEnumerator(afe)

        # TODO(cmasone): populate this from |config|.
        tasks = []

        self._events = [timed_event.Nightly.CreateFromConfig(config, tasks),
                        timed_event.Weekly.CreateFromConfig(config, tasks)]


    def RunForever(self):
        """Main loop of the scheduler.  Runs til the process is killed."""
        while True:
            self.HandleEventsOnce()
            time.sleep(self._LOOP_INTERVAL)


    def HandleEventsOnce(self):
        """One turn through the loop.  Separated out for unit testing."""
        # TODO(cmasone): Make Handle() deal with platforms.
        platforms = self._enumerator.Enumerate()

        for e in self._events:
            if e.ShouldHandle():
                e.Handle(self._scheduler)
