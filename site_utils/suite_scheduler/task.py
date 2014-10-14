# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging, re
import deduping_scheduler
import driver
from distutils import version
from constants import Labels

import common
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.scheduler import scheduler_lib
from autotest_lib.server import site_utils
try:
    from chromite.lib import gs
except ImportError:
    gs = None


class MalformedConfigEntry(Exception):
    """Raised to indicate a failure to parse a Task out of a config."""
    pass


BARE_BRANCHES = ['factory', 'firmware']


def PickBranchName(type, milestone):
    """Pick branch name. If type is among BARE_BRANCHES, return type,
    otherwise, return milestone.

    @param type: type of the branch, e.g., 'release', 'factory', or 'firmware'
    @param milestone: CrOS milestone number
    """
    if type in BARE_BRANCHES:
        return type
    return milestone


class TotMilestoneManager(object):
    """A class capable of converting tot string to milestone numbers.

    This class is used as a cache for the tot milestone, so we don't
    repeatedly hit google storage for all O(100) tasks in suite
    scheduler's ini file.
    """

    __metaclass__ = scheduler_lib.Singleton

    @staticmethod
    def _tot_milestone():
        """Get the tot milestone, eg: R40

        @returns: A string representing the Tot milestone as declared by
            the LATEST_BUILD_URL, or an empty string if LATEST_BUILD_URL
            doesn't exist.
        """
        try:
            return (gs.GSContext().Cat(constants.LATEST_BUILD_URL).split('-')[0]
                    if gs else '')
        except gs.GSNoSuchKey as e:
            logging.warning('Failed to get latest build: %s', e)
            return ''


    def refresh(self):
        """Refresh the tot milestone string managed by this class."""
        self.tot = self._tot_milestone()


    def __init__(self):
        """Initialize a TotMilestoneManager."""
        self.refresh()


    def ConvertTotSpec(self, tot_spec):
        """Converts a tot spec to the appropriate milestone.

        Assume tot is R40:
        tot   -> R40
        tot-1 -> R39
        tot-2 -> R38
        tot-(any other numbers) -> R40

        With the last option one assumes that a malformed configuration that has
        'tot' in it, wants at least tot.

        @param tot_spec: A string representing the tot spec.
        @raises MalformedConfigEntry: If the tot_spec doesn't match the
            expected format.
        """
        tot_spec = tot_spec.lower()
        match = re.match('(tot)[-]?(1$|2$)?', tot_spec)
        if not match:
            raise MalformedConfigEntry(
                    "%s isn't a valid branch spec." % tot_spec)
        tot_mstone = self.tot
        num_back = match.groups()[1]
        if num_back:
            tot_mstone_num = tot_mstone.lstrip('R')
            tot_mstone = tot_mstone.replace(
                    tot_mstone_num, str(int(tot_mstone_num)-int(num_back)))
        return tot_mstone


class Task(object):
    """Represents an entry from the scheduler config.  Can schedule itself.

    Each entry from the scheduler config file maps one-to-one to a
    Task.  Each instance has enough info to schedule itself
    on-demand with the AFE.

    This class also overrides __hash__() and all comparitor methods to enable
    correct use in dicts, sets, etc.
    """


    @staticmethod
    def CreateFromConfigSection(config, section):
        """Create a Task from a section of a config file.

        The section to parse should look like this:
        [TaskName]
        suite: suite_to_run  # Required
        run_on: event_on which to run  # Required
        branch_specs: factory,firmware,>=R12 or ==R12 # Optional
        pool: pool_of_devices  # Optional
        num: sharding_factor  # int, Optional
        boards: board1, board2  # comma seperated string, Optional

        By default, Tasks run on all release branches, not factory or firmware.

        @param config: a ForgivingConfigParser.
        @param section: the section to parse into a Task.
        @return keyword, Task object pair.  One or both will be None on error.
        @raise MalformedConfigEntry if there's a problem parsing |section|.
        """
        if not config.has_section(section):
            raise MalformedConfigEntry('unknown section %s' % section)

        allowed = set(['suite', 'run_on', 'branch_specs', 'pool', 'num',
                       'boards', 'file_bugs'])
        # The parameter of union() is the keys under the section in the config
        # The union merges this with the allowed set, so if any optional keys
        # are omitted, then they're filled in. If any extra keys are present,
        # then they will expand unioned set, causing it to fail the following
        # comparison against the allowed set.
        section_headers = allowed.union(dict(config.items(section)).keys())
        if allowed != section_headers:
            raise MalformedConfigEntry('unknown entries: %s' %
                      ", ".join(map(str, section_headers.difference(allowed))))

        keyword = config.getstring(section, 'run_on')
        suite = config.getstring(section, 'suite')
        branches = config.getstring(section, 'branch_specs')
        pool = config.getstring(section, 'pool')
        boards = config.getstring(section, 'boards')
        file_bugs = config.getboolean(section, 'file_bugs')
        for klass in driver.Driver.EVENT_CLASSES:
            if klass.KEYWORD == keyword:
                priority = klass.PRIORITY
                timeout = klass.TIMEOUT
                break
        else:
            priority = None
            timeout = None
        try:
            num = config.getint(section, 'num')
        except ValueError as e:
            raise MalformedConfigEntry("Ill-specified 'num': %r" %e)
        if not keyword:
            raise MalformedConfigEntry('No event to |run_on|.')
        if not suite:
            raise MalformedConfigEntry('No |suite|')
        specs = []
        if branches:
            specs = re.split('\s*,\s*', branches)
            Task.CheckBranchSpecs(specs)
        return keyword, Task(section, suite, specs, pool, num, boards,
                             priority, timeout,
                             file_bugs=file_bugs if file_bugs else False)


    @staticmethod
    def CheckBranchSpecs(branch_specs):
        """Make sure entries in the list branch_specs are correctly formed.

        We accept any of BARE_BRANCHES in |branch_specs|, as
        well as _one_ string of the form '>=RXX' or '==RXX', where 'RXX' is a
        CrOS milestone number.

        @param branch_specs: an iterable of branch specifiers.
        @raise MalformedConfigEntry if there's a problem parsing |branch_specs|.
        """
        have_seen_numeric_constraint = False
        for branch in branch_specs:
            if branch in BARE_BRANCHES:
                continue
            if not have_seen_numeric_constraint:
                #TODO(beeps): Why was <= dropped on the floor?
                if branch.startswith('>=R') or branch.startswith('==R'):
                    have_seen_numeric_constraint = True
                elif 'tot' in branch:
                    TotMilestoneManager().ConvertTotSpec(
                            branch[branch.index('tot'):])
                    have_seen_numeric_constraint = True
                continue
            raise MalformedConfigEntry("%s isn't a valid branch spec." % branch)


    def __init__(self, name, suite, branch_specs, pool=None, num=None,
                 boards=None, priority=None, timeout=None, file_bugs=False):
        """Constructor

        Given an iterable in |branch_specs|, pre-vetted using CheckBranchSpecs,
        we'll store them such that _FitsSpec() can be used to check whether a
        given branch 'fits' with the specifications passed in here.
        For example, given branch_specs = ['factory', '>=R18'], we'd set things
        up so that _FitsSpec() would return True for 'factory', or 'RXX'
        where XX is a number >= 18. Same check is done for branch_specs = [
        'factory', '==R18'], which limit the test to only one specific branch.

        Given branch_specs = ['factory', 'firmware'], _FitsSpec()
        would pass only those two specific strings.

        Example usage:
          t = Task('Name', 'suite', ['factory', '>=R18'])
          t._FitsSpec('factory')  # True
          t._FitsSpec('R19')  # True
          t._FitsSpec('R17')  # False
          t._FitsSpec('firmware')  # False
          t._FitsSpec('goober')  # False

          t = Task('Name', 'suite', ['factory', '==R18'])
          t._FitsSpec('R19')  # False, branch does not equal to 18
          t._FitsSpec('R18')  # True
          t._FitsSpec('R17')  # False

        @param name: name of this task, e.g. 'NightlyPower'
        @param suite: the name of the suite to run, e.g. 'bvt'
        @param branch_specs: a pre-vetted iterable of branch specifiers,
                             e.g. ['>=R18', 'factory']
        @param pool: the pool of machines to use for scheduling purposes.
                     Default: None
        @param num: the number of devices across which to shard the test suite.
                    Type: integer or None
                    Default: None
        @param boards: A comma seperated list of boards to run this task on.
                       Default: Run on all boards.
        @param priority: The string name of a priority from
                         client.common_lib.priorities.Priority.
        @param timeout: The max lifetime of the suite in hours.
        @param file_bugs: True if bug filing is desired for the suite created
                          for this task.
        """
        self._name = name
        self._suite = suite
        self._branch_specs = branch_specs
        self._pool = pool
        self._num = num
        self._priority = priority
        self._timeout = timeout
        self._file_bugs = file_bugs

        self._bare_branches = []
        self._version_equal_constraint = False
        if not branch_specs:
            # Any milestone is OK.
            self._numeric_constraint = version.LooseVersion('0')
        else:
            self._numeric_constraint = None
            for spec in branch_specs:
                if 'tot' in spec.lower():
                    tot_str = spec[spec.index('tot'):]
                    spec = spec.replace(
                            tot_str, TotMilestoneManager().ConvertTotSpec(
                                tot_str))
                if spec.startswith('>='):
                    self._numeric_constraint = version.LooseVersion(
                        spec.lstrip('>=R'))
                elif spec.startswith('=='):
                    self._version_equal_constraint = True
                    self._numeric_constraint = version.LooseVersion(
                        spec.lstrip('==R'))
                else:
                    self._bare_branches.append(spec)

        # Since we expect __hash__() and other comparitor methods to be used
        # frequently by set operations, and they use str() a lot, pre-compute
        # the string representation of this object.
        if num is None:
            numStr = '[Default num]'
        else:
            numStr = '%d' % num

        if boards is None:
            self._boards = set()
            boardsStr = '[All boards]'
        else:
            self._boards = set([x.strip() for x in boards.split(',')])
            boardsStr = boards

        self._str = ('%s: %s on %s with pool %s, boards [%s], file_bugs = %s '
                     'across %s machines.' % (self.__class__.__name__,
                     suite, branch_specs, pool, boardsStr, self._file_bugs,
                     numStr))


    def _FitsSpec(self, branch):
        """Checks if a branch is deemed OK by this instance's branch specs.

        When called on a branch name, will return whether that branch
        'fits' the specifications stored in self._bare_branches,
        self._numeric_constraint and self._version_equal_constraint.

        @param branch: the branch to check.
        @return True if b 'fits' with stored specs, False otherwise.
        """
        if branch in BARE_BRANCHES:
            return branch in self._bare_branches
        if self._numeric_constraint:
            if self._version_equal_constraint:
                return version.LooseVersion(branch) == self._numeric_constraint
            else:
                return version.LooseVersion(branch) >= self._numeric_constraint
        else:
            return False


    @property
    def name(self):
        """Name of this task, e.g. 'NightlyPower'."""
        return self._name


    @property
    def suite(self):
        """Name of the suite to run, e.g. 'bvt'."""
        return self._suite


    @property
    def branch_specs(self):
        """a pre-vetted iterable of branch specifiers,
        e.g. ['>=R18', 'factory']."""
        return self._branch_specs


    @property
    def pool(self):
        """The pool of machines to use for scheduling purposes."""
        return self._pool


    @property
    def num(self):
        """The number of devices across which to shard the test suite.
        Type: integer or None"""
        return self._num


    @property
    def boards(self):
        """The boards on which to run this suite.
        Type: Iterable of strings"""
        return self._boards


    @property
    def priority(self):
        """The priority of the suite"""
        return self._priority


    @property
    def timeout(self):
        """The maximum lifetime of the suite in hours."""
        return self._timeout


    def __str__(self):
        return self._str


    def __repr__(self):
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


    def AvailableHosts(self, scheduler, board):
        """Query what hosts are able to run a test on a board and pool
        combination.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param board: the board against which one wants to run the test.
        @return The list of hosts meeting the board and pool requirements,
                or None if no hosts were found."""
        if self._boards and board not in self._boards:
            return []

        labels = [Labels.BOARD_PREFIX + board]
        if self._pool:
            labels.append(Labels.POOL_PREFIX + self._pool)

        return scheduler.CheckHostsExist(multiple_labels=labels)


    def ShouldHaveAvailableHosts(self):
        """As a sanity check, return true if we know for certain that
        we should be able to schedule this test. If we claim this test
        should be able to run, and it ends up not being scheduled, then
        a warning will be reported.

        @return True if this test should be able to run, False otherwise.
        """
        return self._pool == 'bvt'


    def Run(self, scheduler, branch_builds, board, force=False):
        """Run this task.  Returns False if it should be destroyed.

        Execute this task.  Attempt to schedule the associated suite.
        Return True if this task should be kept around, False if it
        should be destroyed.  This allows for one-shot Tasks.

        @param scheduler: an instance of DedupingScheduler, as defined in
                          deduping_scheduler.py
        @param branch_builds: a dict mapping branch name to the build(s) to
                              install for that branch, e.g.
                              {'R18': ['x86-alex-release/R18-1655.0.0'],
                               'R19': ['x86-alex-release/R19-2077.0.0']}
        @param board: the board against which to run self._suite.
        @param force: Always schedule the suite.
        @return True if the task should be kept, False if not
        """
        logging.info('Running %s on %s', self._name, board)
        builds = []
        for branch, build in branch_builds.iteritems():
            logging.info('Checking if %s fits spec %r',
                         branch, self.branch_specs)
            if self._FitsSpec(branch):
                builds.extend(build)
        for build in builds:
            try:
                if not scheduler.ScheduleSuite(self._suite, board, build,
                                               self._pool, self._num,
                                               self._priority, self._timeout,
                                               force,
                                               file_bugs=self._file_bugs):
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
        @param branch_builds: a dict mapping branch name to the build(s) to
                              install for that branch, e.g.
                              {'R18': ['x86-alex-release/R18-1655.0.0'],
                               'R19': ['x86-alex-release/R19-2077.0.0']}
        @param board: the board against which to run self._suite.
        @param force: Always schedule the suite.
        @return False
        """
        super(OneShotTask, self).Run(scheduler, branch_builds, board, force)
        return False
