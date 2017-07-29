# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import textwrap

import common

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.server import afe_urls
from autotest_lib.server import site_utils
from autotest_lib.server.cros.dynamic_suite import job_status
from autotest_lib.server.cros.dynamic_suite import reporting_utils
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.site_utils  import gmail_lib

try:
    from chromite.lib import metrics
except ImportError:
    metrics = site_utils.metrics_mock


BUG_CONFIG_SECTION = 'BUG_REPORTING'

CHROMIUM_EMAIL_ADDRESS = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'chromium_email_address', default='')
EMAIL_CREDS_FILE = global_config.global_config.get_config_value(
        'NOTIFICATIONS', 'gmail_api_credentials_test_failure', default=None)


class Bug(object):
    """Holds the minimum information needed to make a dedupable bug report."""

    def __init__(self, title, summary, search_marker=None, labels=None,
                 owner='', cc=None, components=None):
        """
        Initializes Bug object.

        @param title: The title of the bug.
        @param summary: The summary of the bug.
        @param search_marker: The string used to determine if a bug is a
                              duplicate report or not. All Bugs with the same
                              search_marker are considered to be for the same
                              bug. Make this None if you do not want to dedupe.
        @param labels: The labels that the filed bug will have.
        @param owner: The owner/asignee of this bug. Typically left blank.
        @param cc: Who to cc'd for this bug.
        @param components: The components that the filed bug will have.
        """
        self._title = title
        self._summary = summary
        self._search_marker = search_marker
        self.owner = owner

        self.labels = labels if labels is not None else []
        self.components = components if components is not None else []
        self.cc = cc if cc is not None else []


    def title(self):
        """Combines information about this bug into a title string."""
        return self._title


    def summary(self):
        """Combines information about this bug into a summary string."""
        return self._summary


    def search_marker(self):
        """Return an Anchor that we can use to dedupe this exact bug."""
        return self._search_marker


class TestBug(Bug):
    """
    Wrap up all information needed to make an intelligent report about an
    issue. Each TestBug has a search marker associated with it that can be
    used to find similar reports.
    """

    def __init__(self, build, chrome_version, suite, result):
        """
        @param build: The build type, of the form <board>/<milestone>-<release>.
                      eg: x86-mario-release/R25-4321.0.0
        @param chrome_version: The chrome version associated with the build.
                               eg: 28.0.1498.1
        @param suite: The name of the suite that this test run is a part of.
        @param result: The status of the job associated with this issue.
                       This contains the status, job id, test name, hostname
                       and reason for issue.
        """
        self.build = build
        self.chrome_version = chrome_version
        self.suite = suite
        self.name = tools.get_test_name(build, suite, result.test_name)
        self.reason = result.reason
        # The result_owner is used to find results and logs.
        self.result_owner = result.owner
        self.hostname = result.hostname
        self.job_id = result.id

        # Aborts, server/client job failures or a test failure without a
        # reason field need lab attention. Lab bugs for the aborted case
        # are disabled till crbug.com/188217 is resolved.
        self.lab_error = job_status.is_for_infrastructure_fail(result)

        # The owner is who the bug is assigned to.
        self.owner = ''
        self.cc = []
        self.components = []

        if result.is_warn():
            self.labels = ['Test-Warning']
            self.status = 'Warning'
        else:
            self.labels = []
            self.status = 'Failure'


    def title(self):
        """Combines information about this bug into a title string."""
        return '[%s] %s %s on %s' % (self.suite, self.name,
                                     self.status, self.build)


    def summary(self):
        """Combines information about this bug into a summary string."""

        links = self._get_links_for_failure()
        template = ('This report is automatically generated to track the '
                    'following %(status)s:\n'
                    'Test: %(test)s.\n'
                    'Suite: %(suite)s.\n'
                    'Chrome Version: %(chrome_version)s.\n'
                    'Build: %(build)s.\n\nReason:\n%(reason)s.\n'
                    'build artifacts: %(build_artifacts)s.\n'
                    'results log: %(results_log)s.\n'
                    'status log: %(status_log)s.\n'
                    'job link: %(job)s.\n\n'
                    'You may want to check the test history on wmatrix: '
                    '%(test_history_url)s\n'
                    'You may also want to check the test retry dashboard in '
                    'case this is a flakey test: %(retry_url)s\n')

        specifics = {
            'status': self.status,
            'test': self.name,
            'suite': self.suite,
            'build': self.build,
            'chrome_version': self.chrome_version,
            'reason': self.reason,
            'build_artifacts': links.artifacts,
            'results_log': links.results,
            'status_log': links.status_log,
            'buildbot_stages': links.buildbot,
            'job': links.job,
            'test_history_url': links.test_history_url,
            'retry_url': links.retry_url,
        }

        return template % specifics


    # TO-DO(shuqianz) Fix the dedupe failing issue because reason contains
    # special characters after
    # https://bugs.chromium.org/p/monorail/issues/detail?id=806 being fixed.
    def search_marker(self):
        """Return an Anchor that we can use to dedupe this exact bug."""
        board = ''
        try:
            board = site_utils.ParseBuildName(self.build)[0]
        except site_utils.ParseBuildNameException as e:
            logging.error(str(e))

        # Substitute the board name for a placeholder. We try both build and
        # release board name variants.
        reason = self.reason
        if board:
            for b in (board, board.replace('_', '-')):
                reason = reason.replace(b, 'BOARD_PLACEHOLDER')

        return "%s{%s,%s,%s}" % ('Test%s' % self.status, self.suite,
                                 self.name, reason)


    def _get_links_for_failure(self):
        """Returns a named tuple of links related to this failure."""
        links = collections.namedtuple('links', ('results,'
                                                 'status_log,'
                                                 'artifacts,'
                                                 'job,'
                                                 'test_history_url,'
                                                 'retry_url'))
        return links(reporting_utils.link_result_logs(
                         self.job_id, self.result_owner, self.hostname),
                     reporting_utils.link_status_log(
                         self.job_id, self.result_owner, self.hostname),
                     reporting_utils.link_build_artifacts(self.build),
                     reporting_utils.link_job(self.job_id),
                     reporting_utils.link_test_history(self.name),
                     reporting_utils.link_retry_url(self.name))


class MachineKillerBug(Bug):
    """Wrap up information needed to report a test killing a machine."""

    # Label used by the bug-filer to categorize machine killers
    _MACHINE_KILLER_LABEL = 'machine-killer'
    # Address to which this bug will be cc'd
    _CC_ADDRESS = global_config.global_config.get_config_value(
                            'SCHEDULER', 'notify_email_errors', default='')


    def __init__(self, job_id, job_name, machine):
        """Initialize MachineKillerBug.

        @param job_id: The id of the job, this should be an afe job id.
        @param job_name: the name of the job
        @param machine: The hostname of a machine that has been put
                        in Repair Failed by the job.

        """
        # Name of test job may contain information like build and suite.
        # e.g. lumpy-release/R31-1234.0.0/bvt/dummy_Pass_SERVER_JOB
        # Try to split job_name with '/' and use the last part
        # as test name. Note this assumes test name must not contains '/'.
        self._test_name = job_name.rsplit('/', 1)[-1]
        self._job_id = job_id
        self._machine = machine
        self.owner=''
        self.cc=[self._CC_ADDRESS]
        self.labels=[self._MACHINE_KILLER_LABEL]
        self.components = []


    def title(self):
        return ('%s suspected of putting machines in Repair Failed state.'
                 % self._test_name)

    def summary(self):
        """Combines information about this bug into a summary string."""

        template = ('This bug has been automatically filed to track the '
                    'following issue:\n\n'
                    'Test: %(test)s.\n'
                    'Machine: %(machine)s.\n'
                    'Issue: It is suspected that the test has put the '
                    'machine in the Repair Failed State.\n'
                    'Suggested Actions: Investigate to determine if this '
                    'test is at fault and then either fix or disable the '
                    'test if appropriate.\n'
                    'Job link: %(job)s.\n')
        disclaimer = ('\n\nNote that the autofiled count on this bug indicates '
                      'the number of times we have attempted to repair the '
                      'machine, not the number of times it has gone into '
                      'the repair failed state.\n')
        specifics = {
            'test': self._test_name,
            'machine': self._machine,
            'job': reporting_utils.link_job(self._job_id),
        }
        return template % specifics + disclaimer


    def search_marker(self):
        """Returns an Anchor that we can use to dedupe this bug."""
        return 'MachineKiller{%s}' % self._test_name


class PoolHealthBug(Bug):
    """Report information about a critical pool of DUTs in the lab."""

    _POOL_HEALTH_LABELS = global_config.global_config.get_config_value(
            'BUG_REPORTING', 'pool_health_labels', type=list, default=[])
    _POOL_HEALTH_COMPONENTS = global_config.global_config.get_config_value(
            'BUG_REPORTING', 'pool_health_components', type=list, default=[])
    _CC_ADDRESS = global_config.global_config.get_config_value(
            'BUG_REPORTING', 'pool_health_cc', type=list, default=[])
    _SUMMARY_TEMPLATE = textwrap.dedent("""\
    This bug has been automatically filed to track the following issue:

    Not enough DUTs available.
    Pool: {this._pool}
    Board: {this._board}
    DUTs needed: {this._num_required}
    DUTs available: {this._num_available}
    Suite: {this._suite_name}
    Build: {this._build}

    Hosts:

    {host_summaries}
    """)
    _HOST_TEMPLATE = '{host.hostname} {locked_status} {host.status} {afe_link}'

    def __init__(self, exception):
        """Initialize a PoolHealthBug.

        @param exception: NotEnoughDutsError with context information.
        @param hosts: An Iterable of all Hosts with the
            board, in the given pool.
        """
        self._exception = exception
        self._board = exception.board
        self._pool = exception.pool
        self._num_available = exception.num_available
        self._num_required = exception.num_required
        self._bug_id = exception.bug_id
        self._hosts = exception.hosts
        self._suite_name = exception.suite_name
        self._build = exception.build

        self.owner = ''
        self.cc = self._CC_ADDRESS
        self.labels = self._POOL_HEALTH_LABELS
        self.components = self._POOL_HEALTH_COMPONENTS


    def title(self):
        return ('pool: %s, board: %s in critical state' %
                (self._pool, self._board))


    def summary(self):
        """Combines information about this bug into a summary string."""
        return self._SUMMARY_TEMPLATE.format(
            this=self,
            host_summaries='\n'.join(self._make_host_summaries()))


    def _make_host_summaries(self):
        """Yield hosts summary strings."""
        host_template = self._HOST_TEMPLATE
        for host in self._hosts:
            yield host_template.format(
                host=host,
                locked_status='Locked' if host.locked else 'Unlocked',
                afe_link=afe_urls.get_host_url(host.id))


    def search_marker(self):
        """Returns an Anchor that we can use to dedupe this bug."""
        return 'PoolHealthBug{%s, %s}' % (self._pool, self._board)


class SuiteSchedulerBug(Bug):
    """Bug filed for suite scheduler."""

    _SUITE_SCHEDULER_LABELS = ['Build-HardwareLab', 'Pri-1', 'suite_scheduler']

    def __init__(self, suite, build, board, control_file_exception):
        self._suite = suite
        self._build = build
        self._board = board
        self._exception = control_file_exception
        # TODO(fdeng): fix get_sheriffs crbug.com/483254
        lab_deputies = site_utils.get_sheriffs(lab_only=True)
        self.owner = lab_deputies[0] if lab_deputies else ''
        self.labels = self._SUITE_SCHEDULER_LABELS
        self.cc = lab_deputies[1:] if lab_deputies else []
        self.components = []


    def title(self):
        """Return Title of the bug"""
        if isinstance(self._exception, error.ControlFileNotFound):
            t = 'Missing control file'
        else:
            t = 'Problem with getting control file'
        return '[suite scheduler] %s for suite: "%s", build: %s' % (
                t, self._suite, self._build)


    def summary(self):
        """Combines information about this bug into a summary string."""
        template = ('Suite scheduler could not schedule suite due to '
                    'a control file problem:\n\n'
                    'Suite:\t%(suite)s\n'
                    'Build:\t%(build)s\n'
                    'Board:\t%(board)s (The problem may happen for other '
                    'boards as well, only the first board is reported.)\n'
                    'Diagnose:\n%(diagnose)s\n')

        if isinstance(self._exception, error.ControlFileNotFound):
            diagnose = (
                    '\tThe suite\'s control file does not exist in the build.\n'
                    '\tDo you expect the suite to run for the said build?\n'
                    '\t- If yes, please add/backport the control file to '
                    'the build,\n'
                    '\t- If not, please fix the entry for this suite in '
                    'suite_scheduler.ini so that it specifies the '
                    'right builds to run;\n'
                    '\t  and request a push to prod.')
        else:
            diagnose = ('\tNo suggestion. Please ask infra deputy '
                        'to triage.\n%s\n') % str(self._exception)
        specifics = {'suite': self._suite,
                     'build': self._build,
                     'board': self._board,
                     'error': type(self._exception),
                     'diagnose': diagnose,}
        return template % specifics


    def search_marker(self):
        """Returns an Anchor that we can use to dedupe this bug."""
        # TODO(fdeng): flaky deduping behavior, see crbug.com/486895
        return 'SuiteSchedulerBug{%s, %s}' % (
                self._suite, type(self._exception).__name__)


ReportResult = collections.namedtuple('ReportResult', ['bug_id', 'update_count'])


class NullReporter(object):
    """Null object for bug reporter."""

    def report(self, bug, bug_template=None, ignore_duplicate=False):
        """Report an issue to the bug tracker.

        If this issue has happened before, post a comment on the
        existing bug about it occurring again, and update the
        'autofiled-count' label.  If this is a new issue, create a
        new bug for it.

        @param bug          A Bug instance about the issue.
        @param bug_template A template dictionary specifying the
                            default bug filing options for an issue
                            with this suite.
        @param ignore_duplicate  If True, when a duplicate is found,
                                 simply ignore the new one rather than
                                 posting an update.
        @return   A ReportResult namedtuple containing:

                  - the issue id as a string or None
                  - the number of times the bug has been updated.  For a new
                    bug, the count is 1.  If we could not file a bug for some
                    reason, the count is 0.
        """
        return ReportResult(None, 0)


def send_email(bug, bug_template):
    """Send email to the owner and cc's to notify the TestBug.

    @param bug: TestBug instance.
    @param bug_template: A template dictionary specifying the default bug
                         filing options for failures in this suite.
    """
    to_set = set(bug.cc) if bug.cc else set()
    if bug.owner:
        to_set.add(bug.owner)
    if bug_template.get('cc'):
        to_set = to_set.union(bug_template.get('cc'))
    if bug_template.get('owner'):
        to_set.add(bug_template.get('owner'))
    recipients = ', '.join(to_set)
    if not recipients:
        logging.warning('No owner/cc found. Will skip sending a mail.')
        return
    success = False
    try:
        gmail_lib.send_email(
            recipients, bug.title(), bug.summary(), retry=False,
            creds_path=site_utils.get_creds_abspath(EMAIL_CREDS_FILE))
        success = True
    finally:
        (metrics.Counter('chromeos/autotest/errors/send_bug_email')
         .increment(fields={'success': success}))
