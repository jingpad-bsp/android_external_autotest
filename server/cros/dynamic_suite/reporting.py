# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import json

# We need to import common to be able to import chromite and requests.
import common

from autotest_lib.client.common_lib import global_config

try:
    __import__('chromite')
except ImportError, e:
    have_chromite = False
    logging.info("Bug filing disabled. %s", e)
else:
    from chromite.lib import cros_build_lib, gdata_lib, gs
    have_chromite = True


BUG_CONFIG_SECTION = 'BUG_REPORTING'


class TestFailure(object):
    """Wrap up all information needed to make an intelligent report about a
    test failure.

    Each TestFailure has a search marker associated with it that can be used to
    find reports of the same error."""

    # global configurations needed for build artifacts
    _gs_domain = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'gs_domain', default='')
    _chromeos_image_archive = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'chromeos_image_archive', default='')
    _arg_prefix = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'arg_prefix', default='')

    # global configurations needed for results log
    _retrieve_logs_cgi = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'retrieve_logs_cgi', default='')
    _generic_results_bin = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'generic_results_bin', default='')
    _debug_dir = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'debug_dir', default='')

    # gs prefix to perform file like operations (gs://)
    _gs_file_prefix = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'gs_file_prefix', default='')

    # global configurations needed for buildbot stages link
    _buildbot_builders = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'buildbot_builders', default='')
    _build_prefix = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'build_prefix', default='')

    # Number of times to retry if a gs command fails. Defaults to 10,
    # which is far too long given that we already wait on these files
    # before starting HWTests.
    _GS_RETRIES = 1


    _HTTP_ERROR_THRESHOLD = 400

    def __init__(self, build, suite, test, reason, owner, hostname, job_id):
        """
        @param build The build type, of the form <board>/<milestone>-<release>.
                     ie. x86-mario-release/R25-4321.0.0
        @param suite The name of the suite that this test run was a part of.
        @param test The name of the test that this failure is about.
        @param reason The reason that this test failed.
        @param owner The owner of the test that failed.
        @param hostname The host this test failure occured on.
        @param job_id The id of the test that failed.
        """
        self.build = build
        self.suite = suite
        self.test = test
        self.reason = reason
        self.owner = owner
        self.hostname = hostname
        self.job_id = job_id


    def bug_title(self):
        """Converts information about a failure into a string appropriate to
        be the title of a bug."""
        return '[%s] %s failed on %s' % (self.suite, self.test, self.build)


    def bug_summary(self):
        """
        Converts information about this failure into a string appropriate
        to be the summary of this bug. Includes the reason field and links
        to the build artifacts and results.
        """

        links = self._get_links_for_failure()
        summary = ('This bug has been automatically filed to track the '
                   'following failure:\nTest: %(test)s.\nSuite: %(suite)s.\n'
                   'Build: %(build)s.\n\nReason:\n%(reason)s.\n\n'
                   'build artifacts: %(build_artifacts)s.\n'
                   'results log: %(results_log)s.\n'
                   'buildbot stages: %(buildbot_stages)s.\n')
        specifics = {
            'test': self.test,
            'suite': self.suite,
            'build': self.build,
            'reason': self.reason,
            'build_artifacts': links.artifacts,
            'results_log': links.results,
            'buildbot_stages': links.buildbot,
        }
        return summary % specifics


    def search_marker(self):
        """When filing a report about this failure, include the returned line in
        the report to provide a way to search for this exact failure."""
        return "%s(%s,%s,%s)" % ('TestFailure', self.suite,
                                    self.test, self.reason)


    def _link_build_artifacts(self):
        """
        Link to the build artifacts.

        @return: url to build artifacts on google storage.
        """
        return (self._gs_domain + self._arg_prefix +
                self._chromeos_image_archive + self.build)


    def _link_result_logs(self):
        """
        Link to test failure logs.

        @return: url to test logs on google storage.
        """
        if self.job_id and self.owner and self.hostname:
            path_to_object = '%s-%s/%s/%s' % (self.job_id, self.owner,
                                              self.hostname, self._debug_dir)
            return (self._retrieve_logs_cgi + self._generic_results_bin +
                    path_to_object)
        return 'NA'


    def _get_metadata_dict(self):
        """
        Get a dictionary of metadata related to this failure.

        Metadata.json is created in the HWTest Archiving stage, if this file
        isn't found the call to Cat will timeout after the number of retries
        specified in the GSContext object. If metadata.json exists we parse
        a json string of it's contents into a dictionary, which we return.

        @return: a dictionary with the contents of metadata.json.
        """
        if not have_chromite:
            return
        try:
            gs_context = gs.GSContext(retries=self._GS_RETRIES)
            gs_cmd = '%s%s%s/metadata.json' % (self._gs_file_prefix,
                                               self._chromeos_image_archive,
                                               self.build)
            return json.loads(gs_context.Cat(gs_cmd).output)
        except cros_build_lib.RunCommandError, e:
            logging.debug(e)


    def _link_buildbot_stages(self):
        """
        Link to the buildbot page associated with this run of HWTests.

        @return: A link to the buildbot stages page, or 'NA' if we cannot glean
                 enough information from metadata.json (or it doesn't exist).
        """
        metadata = self._get_metadata_dict()
        if (metadata and
            metadata.get('builder-name') and
            metadata.get('build-number')):

            return '%s%s/builds/%s' % (self._buildbot_builders,
                                       metadata.get('builder-name'),
                                       metadata.get('build-number'))
        return 'NA'


    def _get_links_for_failure(self):
        """
        Get links related to this test failure.

        @return: Returns a named tuple of links.
        """
        links = collections.namedtuple('links', ('results,'
                                                 'artifacts,'
                                                 'buildbot'))
        return links(self._link_result_logs(),
                     self._link_build_artifacts(),
                     self._link_buildbot_stages())


class Reporter(object):
    """Files external reports about bug failures that happened inside of
    autotest."""


    _project_name = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'project_name', default='')
    _username = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'username', default='')
    _password = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'password', default='')
    _SEARCH_MARKER = 'ANCHOR  '


    def _get_tracker(self, project, user, password):
        """ Gets an initialized tracker object. """
        if project and user and password:
            creds = gdata_lib.Creds()
            creds.SetCreds(user, password)
            tracker = gdata_lib.TrackerComm()
            tracker.Connect(creds, project)
            return tracker
        logging.error('Tracker auth not set up in shadow_config.ini, '
                      'cannot file bugs.')
        return None


    def __init__(self):
        if not have_chromite:
            logging.warning("Bug filing disabled due to missing imports.")
            return

        self._tracker = self._get_tracker(self._project_name,
                                          self._username, self._password)


    def _check_tracker(self):
        """
        Checks if we have a tracker object to use for filing bugs.

        @return: True if we have a tracker object.
        """
        return have_chromite and self._tracker


    def report(self, failure):
        """
        Report about a failure on the bug tracker. If this failure has already
        happened, post a comment on the existing bug about it occurring again.
        If this is a new failure, create a new bug about it.

        @param failure A TestFailure instance about the failure.
        """
        if not self._check_tracker():
            logging.error("Can't file %s", failure.bug_title())
            return

        issue = self._find_issue_by_marker(failure.search_marker())
        summary = '%s\n\n%s%s\n' % (failure.bug_summary(),
                                    self._SEARCH_MARKER,
                                    failure.search_marker())
        self._add_issue_to_tracker(issue, summary, failure.bug_title())


    def _add_issue_to_tracker(self, issue, summary, title):
        """
        Adds an issue to the tracker.

        Either file a new issue or append a comment to an existing issue.

        @param issue: The new issue.
        @param summary: A summary of the failure.
        @param title: Title of the bug. If a bug already exists the summary gets
            prefixed with the title.

        @return: None
        """
        if issue:
            summary = '%s\n\n%s' % (title, summary)
            self._tracker.AppendTrackerIssueById(issue.id, summary)
            logging.info("Filed comment %s on %s", summary, issue.id)
        else:
            issue = gdata_lib.Issue(title=title, summary=summary,
                labels=['Test-Support', 'autofiled'],
                status='Untriaged', owner='')
            bugid = self._tracker.CreateTrackerIssue(issue)
            logging.info("Filing new bug %s, with summary %s", bugid,
                                                               summary)


    def _find_issue_by_marker(self, marker):
        """
        Queries the tracker to find if there is a bug filed for this issue.

        @param marker The marker string to search for to find a duplicate of
                     this issue.
        @return A gdata_lib.Issue instance of the issue that was found, or
                None if no issue was found.
        """

        # This will return at most 25 matches, as that's how the
        # code.google.com API limits this query.
        issues = self._tracker.GetTrackerIssuesByText(
                self._SEARCH_MARKER + marker)

        # TODO(milleral) The tracker doesn't support exact text searching, even
        # with quotes around the search term. Therefore, to hack around this, we
        # need to filter through the results we get back and search for the
        # string ourselves.
        # We could have gotten no results...
        if not issues:
            return None

        # We could have gotten some results, but we need to wade through them
        # to find if there's an actually correct one.
        for issue in issues:
            if marker in issue.summary:
                return issue
            for comment in issue.comments:
                # Sometimes, comment.text is None...
                if comment.text and marker in comment.text:
                    return issue

        # Or, if we make it this far, we have only gotten similar, but not
        # actually matching results.
        return None
