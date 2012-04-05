# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import deduping_scheduler, forgiving_config_parser
import logging, re


class MalformedConfigEntry(Exception):
    """Raised to indicate a failure to parse a Task out of a config."""
    pass


class Task(object):
    """Represents an entry from the scheduler config.  Can schedule itself.

    Each entry from the scheduler config file maps one-to-one to a
    Task.  Each instance has enough info to schedule itself
    on-demand with the AFE.

    This class also overrides __hash__() and all comparitor methods to enable
    correct use in dicts, sets, etc.
    """

    _BARE_BRANCHES = ['factory', 'firmware']


    @staticmethod
    def CreateFromConfigSection(config, section):
        """Create a Task from a section of a config file.

        The section to parse should look like this:
        [TaskName]
        suite: suite_to_run  # Required
        run_on: event_on which to run  # Required
        branch_specs: factory,firmware,>=R12  # Optional
        pool: pool_of_devices  # Optional

        @param config: a ForgivingConfigParser.
        @param section: the section to parse into a Task.
        @return keyword, Task object pair.  One or both will be None on error.
        @raise MalformedConfigEntry if there's a problem parsing |section|.
        """
        keyword = config.getstring(section, 'run_on')
        suite = config.getstring(section, 'suite')
        branches = config.getstring(section, 'branch_specs')
        pool = config.getstring(section, 'pool')
        if not keyword:
            raise MalformedConfigEntry('No event to |run_on|.')
        if not suite:
            raise MalformedConfigEntry('No |suite|')
        specs = []
        if branches:
            specs = re.split('\s*,\s*', branches)
            Task.CheckBranchSpecs(specs)
        return keyword, Task(suite, specs, pool)


    @staticmethod
    def CheckBranchSpecs(branch_specs):
        """Make sure entries in the list branch_specs are correctly formed.

        We accept any of Task._BARE_BRANCHES in |branch_specs|, as
        well as _one_ string of the form '>=RXX', where 'RXX' is a
        CrOS milestone number.

        @param branch_specs: an iterable of branch specifiers.
        @raise MalformedConfigEntry if there's a problem parsing |branch_specs|.
        """
        have_seen_numeric_constraint = False
        for branch in branch_specs:
            if branch in Task._BARE_BRANCHES:
                continue
            if branch.startswith('>=R') and not have_seen_numeric_constraint:
                have_seen_numeric_constraint = True
                continue
            raise MalformedConfigEntry('%s is not a valid branch spec.', branch)


    def __init__(self, suite, branch_specs, pool=None):
        """Constructor

        Given an iterable in |branch_specs|, pre-vetted using CheckBranchSpecs,
        we'll store them such that _FitsSpec() can be used to check whether a
        given branch 'fits' with the specifications passed in here.
        For example, given branch_specs = ['factory', '>=R18'], we'd set things
        up so that _FitsSpec() would return True for 'factory', or 'RXX'
        where XX is a number >= 18.

        Given branch_specs = ['factory', 'firmware'], _FitsSpec()
        would pass only those two specific strings.

        Example usage:
          t = Task('suite', ['factory', '>=R18'])
          t._FitsSpec('factory')  # True
          t._FitsSpec('R19')  # True
          t._FitsSpec('R17')  # False
          t._FitsSpec('firmware')  # False
          t._FitsSpec('goober')  # False

        @param suite: the name of the suite to run, e.g. 'bvt'
        @param branch_specs: a pre-vetted iterable of branch specifiers,
                             e.g. ['>=R18', 'factory']
        @param pool: the pool of machines to use for scheduling purposes.
                     Default: None
        """
        self._suite = suite
        self._branch_specs = branch_specs
        self._pool = pool

        self._bare_branches = []
        self._numeric_constraint = ''
        for spec in branch_specs:
            if spec.startswith('>='):
                self._numeric_constraint = spec.lstrip('>=')
            else:
                self._bare_branches.append(spec)

        # Since we expect __hash__() and other comparitor methods to be used
        # frequently by set operations, and they use str() a lot, pre-compute
        # the string representation of this object.
        self._str = '%s: %s on %s with pool %s' % (self.__class__.__name__,
                                                   suite, branch_specs, pool)


    def _FitsSpec(self, branch):
        """Checks if a branch is deemed OK by this instance's branch specs.

        When called on a branch name, will return whether that branch
        'fits' the specifications stored in self._bare_branches and
        self._numeric_constraint.

        @param branch: the branch to check.
        @return True if b 'fits' with stored specs, False otherwise.
        """
        return (branch in self._bare_branches or
                branch >= self._numeric_constraint)


    @property
    def suite(self):
        return self._suite


    @property
    def branch_specs(self):
        return self._branch_specs


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


    def Run(self, scheduler, branch_builds, board, force=False):
        """Run this task.  Returns False if it should be destroyed.

        Execute this task.  Attempt to schedule the associated suite.
        Return True if this task should be kept around, False if it
        should be destroyed.  This allows for one-shot Tasks.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param branch_builds: a dict mapping branch name to the build to
                              install for that branch, e.g.
                              {'R18': 'x86-alex-release/R18-1655.0.0-a1-b1584',
                               'R19': 'x86-alex-release/R19-2077.0.0-a1-b2056'}
        @param board: the board against which to run self._suite.
        @param force: Always schedule the suite.
        @return True if the task should be kept, False if not
        """
        builds = []
        for branch,build in branch_builds.iteritems():
            if self._FitsSpec(branch):
                builds.append(build)
        for build in builds:
            try:
                if not scheduler.ScheduleSuite(self._suite, board, build,
                                               self._pool, force):
                    logging.info('Skipping scheduling %s on %s for %s',
                                 self._suite, build, board)
            except deduping_scheduler.DedupingSchedulerException as e:
                logging.error(e)
        return True


class OneShotTask(Task):
    """A Task that can be run only once.  Can schedule itself."""


    def Run(self, scheduler, branch_builds, board, force=False):
        """Run this task.  Returns False, indicating it should be destroyed.

        Run this task.  Attempt to schedule the associated suite.
        Return False, indicating to the caller that it should discard this task.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param branch_builds: a dict mapping branch name to the build to
                              install for that branch, e.g.
                              {'beta': 'x86-alex-release/R18-1655.0.0-a1-b1584',
                               'dev': 'x86-alex-release/R19-2077.0.0-a1-b2056'}
        @param board: the board against which to run self._suite.
        @param force: Always schedule the suite.
        @return False
        """
        super(OneShotTask, self).Run(scheduler, branch_builds, board, force)
        return False
