# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

import base_event, board_enumerator, build_event
import task, timed_event

import common
from autotest_lib.server import utils

class Driver(object):
    """Implements the main loop of the suite_scheduler.

    @var EVENT_CLASSES: list of the event classes Driver supports.
    @var _LOOP_INTERVAL_SECONDS: seconds to wait between loop iterations.

    @var _scheduler: a DedupingScheduler, used to schedule jobs with the AFE.
    @var _enumerator: a BoardEnumerator, used to list plaforms known to
                      the AFE
    @var _events: dict of BaseEvents to be handled each time through main loop.
    """

    EVENT_CLASSES = [timed_event.Nightly, timed_event.Weekly,
                     build_event.NewBuild]
    _LOOP_INTERVAL_SECONDS = 5 * 60


    def __init__(self, scheduler, enumerator):
        """Constructor

        @param scheduler: an instance of deduping_scheduler.DedupingScheduler.
        @param enumerator: an instance of board_enumerator.BoardEnumerator.
        """
        self._scheduler = scheduler
        self._enumerator = enumerator


    def RereadAndReprocessConfig(self, config, mv):
        """Re-read config, re-populate self._events and recreate task lists.

        @param config: an instance of ForgivingConfigParser.
        @param mv: an instance of ManifestVersions.
        """
        config.reread()
        new_events = self._CreateEventsWithTasks(config, mv)
        for keyword, event in self._events.iteritems():
            event.Merge(new_events[keyword])


    def SetUpEventsAndTasks(self, config, mv):
        """Populate self._events and create task lists from config.

        @param config: an instance of ForgivingConfigParser.
        @param mv: an instance of ManifestVersions.
        """
        self._events = self._CreateEventsWithTasks(config, mv)


    def _CreateEventsWithTasks(self, config, mv):
        """Create task lists from config, and assign to newly-minted events.

        Calling multiple times should start afresh each time.

        @param config: an instance of ForgivingConfigParser.
        @param mv: an instance of ManifestVersions.
        """
        events = {}
        for klass in self.EVENT_CLASSES:
            events[klass.KEYWORD] = klass.CreateFromConfig(config, mv)

        tasks = self.TasksFromConfig(config)
        for keyword, task_list in tasks.iteritems():
            if keyword in events:
                events[keyword].tasks = task_list
            else:
                logging.warning('%s, is an unknown keyword.', keyword)
        return events


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
            if not base_event.HonoredSection(section):
                try:
                    keyword, new_task = task.Task.CreateFromConfigSection(
                        config, section)
                except task.MalformedConfigEntry as e:
                    logging.warning('%s is malformed: %s', section, e)
                    continue
                tasks.setdefault(keyword, []).append(new_task)
        return tasks


    def RunForever(self, config, mv):
        """Main loop of the scheduler.  Runs til the process is killed.

        @param config: an instance of ForgivingConfigParser.
        @param mv: an instance of manifest_versions.ManifestVersions.
        """
        for event in self._events.itervalues():
            event.Prepare()
        while True:
            try:
                self.HandleEventsOnce(mv)
            except board_enumerator.EnumeratorException as e:
                logging.warning('Failed to enumerate boards: %r', e)
            mv.Update()
            task.TotMilestoneManager().refresh()
            time.sleep(self._LOOP_INTERVAL_SECONDS)
            self.RereadAndReprocessConfig(config, mv)


    def HandleEventsOnce(self, mv):
        """One turn through the loop.  Separated out for unit testing.

        @param mv: an instance of manifest_versions.ManifestVersions.
        @raise EnumeratorException if we can't enumerate any supported boards.
        """
        boards = self._enumerator.Enumerate()
        logging.info('Boards currently in the lab: %r', boards)
        for e in self._events.itervalues():
            if e.ShouldHandle():
                logging.info('Handling %s event', e.keyword)
                for board in boards:
                    branch_builds = e.GetBranchBuildsForBoard(board)
                    e.Handle(self._scheduler, branch_builds, board)
                e.UpdateCriteria()


    def ForceEventsOnceForBuild(self, keywords, build_name):
        """Force events with provided keywords to happen, with given build.

        @param keywords: iterable of event keywords to force
        @param build_name: instead of looking up builds to test, test this one.
        """
        board, type, milestone, manifest = utils.ParseBuildName(build_name)
        branch_builds = {task.PickBranchName(type, milestone): [build_name]}
        logging.info('Testing build R%s-%s on %s', milestone, manifest, board)

        for e in self._events.itervalues():
            if e.keyword in keywords:
                e.Handle(self._scheduler, branch_builds, board, force=True)
