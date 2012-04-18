# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

import base_event, board_enumerator, build_event, deduping_scheduler
import forgiving_config_parser, manifest_versions, task, timed_event


class Driver(object):
    """Implements the main loop of the suite_scheduler.

    @var _LOOP_INTERVAL_SECONDS: seconds to wait between loop iterations.

    @var _scheduler: a DedupingScheduler, used to schedule jobs with the AFE.
    @var _enumerator: a BoardEnumerator, used to list plaforms known to
                      the AFE
    @var _events: list of BaseEvents to be handled each time through main loop.
    """

    _LOOP_INTERVAL_SECONDS = 5 * 60


    def __init__(self, scheduler, enumerator):
        """Constructor

        @param scheduler: an instance of deduping_scheduler.DedupingScheduler.
        @param enumerator: an instance of board_enumerator.BoardEnumerator.
        """
        self._scheduler = scheduler
        self._enumerator = enumerator


    def SetUpEventsAndTasks(self, config, mv):
        """Populate self._events and create task lists from config.

        @param config: an instance of ForgivingConfigParser.
        @param mv: an instance of ManifestVersions.
        """
        self._events = [timed_event.Nightly.CreateFromConfig(config, mv),
                        timed_event.Weekly.CreateFromConfig(config, mv),
                        build_event.NewBuild.CreateFromConfig(config, mv)]

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
            if not base_event.HonoredSection(section):
                try:
                    keyword, new_task = task.Task.CreateFromConfigSection(
                        config, section)
                except task.MalformedConfigEntry as e:
                    logging.warn('%s is malformed: %s', section, e)
                    continue
                tasks.setdefault(keyword, []).append(new_task)
        return tasks


    def RunForever(self, mv):
        """Main loop of the scheduler.  Runs til the process is killed.

        @param mv: an instance of manifest_versions.ManifestVersions.
        """
        while True:
            self.HandleEventsOnce(mv)
            mv.Update()
            # TODO(cmasone): Do we want to run every _LOOP_INTERVAL_SECONDS?
            #                Or is it OK to wait that long between every run?
            time.sleep(self._LOOP_INTERVAL_SECONDS)


    def HandleEventsOnce(self, mv):
        """One turn through the loop.  Separated out for unit testing.

        @param mv: an instance of manifest_versions.ManifestVersions.
        """
        boards = self._enumerator.Enumerate()
        logging.info('Running suites for boards: %r', boards)
        for e in self._events:
            if e.ShouldHandle():
                logging.debug('Handling %s event', e.keyword)
                for board in boards:
                    branch_builds = e.GetBranchBuildsForBoard(board, mv)
                    e.Handle(self._scheduler, branch_builds, board)


    def ForceEventsOnceForBuild(self, keywords, build_name):
        """Force events with provided keywords to happen, with given build.

        @param keywords: iterable of event keywords to force
        @param build_name: instead of looking up builds to test, test this one.
        """
        board, type, milestone, manifest = base_event.ParseBuildName(build_name)
        branch_builds = {task.PickBranchName(type, milestone): build_name}
        logging.info('Testing build %s-%s on %s' % (milestone, manifest, board))

        for e in self._events:
            if e.keyword in keywords:
                e.Handle(self._scheduler, branch_builds, board, force=True)
