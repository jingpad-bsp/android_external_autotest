# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.common_lib import error
from autotest_lib.server import site_utils
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers, reporting

class DedupingSchedulerException(Exception):
    """Base class for exceptions from this module."""
    pass


class ScheduleException(DedupingSchedulerException):
    """Raised when an error is returned from the AFE during scheduling."""
    pass


class DedupException(DedupingSchedulerException):
    """Raised when an error occurs while checking for duplicate jobs."""
    pass


class DedupingScheduler(object):
    """A class that will schedule suites to run on a given board, build.

    Includes logic to check whether or not a given (suite, board, build)
    has already been run.  If so, it will skip scheduling that suite.

    @var _afe: a frontend.AFE instance used to talk to autotest.
    """


    def __init__(self, afe=None, file_bug=False):
        """Constructor

        @param afe: an instance of AFE as defined in server/frontend.py.
                    Defaults to a frontend_wrappers.RetryingAFE instance.
        """
        self._afe = afe or frontend_wrappers.RetryingAFE(timeout_min=30,
                                                         delay_sec=10,
                                                         debug=False)
        self._file_bug = file_bug


    def _ShouldScheduleSuite(self, suite, board, build):
        """Return True if |suite| has not yet been run for |build| on |board|.

        True if |suite| has not been run for |build| on |board|, and
        the lab is open for this particular request.  False otherwise.

        @param suite: the name of the suite to run, e.g. 'bvt'
        @param board: the board to run the suite on, e.g. x86-alex
        @param build: the build to install e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @return False if the suite was already scheduled, True if not
        @raise DedupException if the AFE raises while searching for jobs.
        """
        try:
            site_utils.check_lab_status(build)
        except site_utils.TestLabException as ex:
            logging.debug('Skipping suite %s, board %s, build %s:  %s',
                          suite, board, build, str(ex))
            return False
        try:
            return not self._afe.get_jobs(name__startswith=build,
                                          name__endswith='control.'+suite)
        except Exception as e:
            raise DedupException(e)


    # TODO(fdeng): Add status='Available' back into the bug submittal;
    # right now it will be marked as Unconfirmed.
    def _ReportBug(self, title, description):
        """File a bug using bug reporter.

        @param title: A string, representing the bug title.
        @param description: A string, representing the bug description.
        @return: The id of the issue that was created,
                 or None if bug is not filed.
        """
        if not self._file_bug:
            return None
        lab_sheriff = site_utils.get_sheriffs(lab_only=True)
        logging.info('Filing a bug: %s', title)
        return reporting.submit_generic_bug_report(
            title=title,
            summary=description,
            cc=lab_sheriff,
            labels=['Hardware-lab'])


    def _Schedule(self, suite, board, build, pool, num, priority, timeout,
                  file_bugs=False):
        """Schedule |suite|, if it hasn't already been run.

        @param suite: the name of the suite to run, e.g. 'bvt'
        @param board: the board to run the suite on, e.g. x86-alex
        @param build: the build to install e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param pool: the pool of machines to use for scheduling purposes.
                     Default: None
        @param num: the number of devices across which to shard the test suite.
                    Type: integer or None
                    Default: None (uses sharding factor in global_config.ini).
        @param priority: One of the values from
                         client.common_lib.priorities.Priority.
        @param timeout: The max lifetime of the suite in hours.
        @param file_bugs: True if bug filing is desired for this suite.
        @return True if the suite got scheduled
        @raise ScheduleException if an error occurs while scheduling.
        """
        try:
            logging.info('Scheduling %s on %s against %s (pool: %s)',
                         suite, build, board, pool)
            if self._afe.run(
                        'create_suite_job', name=suite, board=board,
                        build=build, check_hosts=False, num=num, pool=pool,
                        priority=priority, timeout=timeout, file_bugs=file_bugs,
                        wait_for_results=file_bugs) is not None:
                return True
            else:
                raise ScheduleException(
                    "Can't schedule %s for %s." % (suite, build))
        except (error.ControlFileNotFound, error.ControlFileEmpty,
                error.ControlFileMalformed, error.NoControlFileList) as e:
            title = ('Exception "%s" occurs when scheduling %s on '
                     '%s against %s (pool: %s)' %
                     (e.__class__.__name__, suite, build, board, pool))
            if self._ReportBug(title, str(e)) is None:
                # Raise the exception if not filing or failed to file a bug.
                raise ScheduleException(e)
            else:
                return False
        except Exception as e:
            raise ScheduleException(e)


    def ScheduleSuite(self, suite, board, build, pool, num, priority, timeout,
                      force=False, file_bugs=False):
        """Schedule |suite|, if it hasn't already been run.

        If |suite| has not already been run against |build| on |board|,
        schedule it and return True.  If it has, return False.

        @param suite: the name of the suite to run, e.g. 'bvt'
        @param board: the board to run the suite on, e.g. x86-alex
        @param build: the build to install e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param pool: the pool of machines to use for scheduling purposes.
        @param num: the number of devices across which to shard the test suite.
                    Type: integer or None
        @param priority: One of the values from
                         client.common_lib.priorities.Priority.
        @param timeout: The max lifetime of the suite in hours.
        @param force: Always schedule the suite.
        @param file_bugs: True if bug filing is desired for this suite.
        @return True if the suite got scheduled, False if not
        @raise DedupException if we can't check for dups.
        @raise ScheduleException if the suite cannot be scheduled.
        """
        if force or self._ShouldScheduleSuite(suite, board, build):
            return self._Schedule(suite, board, build, pool, num, priority,
                                  timeout, file_bugs=file_bugs)
        return False


    def CheckHostsExist(self, *args, **kwargs):
        """Forward a request to check if hosts matching args, kwargs exist."""
        return self._afe.get_hostnames(*args, **kwargs)
