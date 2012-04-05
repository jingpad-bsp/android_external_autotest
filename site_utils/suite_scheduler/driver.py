# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

import deduping_scheduler, forgiving_config_parser, board_enumerator
import task, timed_event


class Driver(object):
    """Implements the main loop of the suite_scheduler.

    @var _LOOP_INTERVAL: time to wait between loop iterations.

    @var _scheduler: a DedupingScheduler, used to schedule jobs with the AFE.
    @var _enumerator: a BoardEnumerator, used to list plaforms known to
                      the AFE
    @var _events: list of BaseEvents to be handled each time through main loop.
    """

    _LOOP_INTERVAL = 5


    def __init__(self, afe):
        """Constructor

        @param afe: an instance of AFE as defined in server/frontend.py.
        @param config: an instance of ForgivingConfigParser.
        """
        self._scheduler = deduping_scheduler.DedupingScheduler(afe)
        self._enumerator = board_enumerator.BoardEnumerator(afe)


    def SetUpEventsAndTasks(self, config):
        """Constructor
        @param config: an instance of ForgivingConfigParser.
        """
        self._events = [timed_event.Nightly.CreateFromConfig(config),
                        timed_event.Weekly.CreateFromConfig(config)]

        tasks = self.TasksFromConfig(config)

        for event in self._events:
            if event.keyword in tasks:
                event.tasks = tasks[event.keyword]
        # TODO(cmasone): warn about unknown keywords?


    def TasksFromConfig(self, config):
        """Generate a dict of {event_keyword: [tasks]} mappings from |config|.

        For each section in |config| that encodes a Task, instantiate a Task
        object.  Determine the event that Task is supposed to run_on and
        append the object to a list associated with the appropriate event
        keyword.  Return a dictionary of these keyword: list of task mappings.

        @param config: a ForgivingConfigParser containing tasks to be parsed.
        @return dict of {event_keyword: [tasks]} mappings.
        @raise MalformedConfigEntry on a task parsing error.
        """
        tasks = {}
        for section in config.sections():
            if not timed_event.TimedEvent.HonorsSection(section):
                try:
                    keyword, new_task = task.Task.CreateFromConfigSection(
                        config, section)
                except task.MalformedConfigEntry as e:
                    logging.warn('%s is malformed: %s', section, e)
                    continue
                tasks.setdefault(keyword, []).append(new_task)
        return tasks


    def RunForever(self):
        """Main loop of the scheduler.  Runs til the process is killed."""
        while True:
            self.HandleEventsOnce()
            time.sleep(self._LOOP_INTERVAL)


    def HandleEventsOnce(self):
        """One turn through the loop.  Separated out for unit testing."""
        boards = self._enumerator.Enumerate()

        branch_builds = {}

        for e in self._events:
            if e.ShouldHandle():
                for board in boards:
                    # TODO(cmasone): determine branch_builds per board.
                    e.Handle(self._scheduler, branch_builds, board)
