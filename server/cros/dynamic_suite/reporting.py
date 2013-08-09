#pylint: disable-msg=W0611
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cgi
import collections
import HTMLParser
import json
import logging
import re

from xml.parsers import expat

import common

from autotest_lib.client.common_lib import global_config
from autotest_lib.server import site_utils
from autotest_lib.server.cros.dynamic_suite import job_status

# Try importing the essential bug reporting libraries. Chromite and gdata_lib
# are useless unless they can import gdata too.
try:
    __import__('chromite')
    __import__('gdata')
    from autotest_lib.site_utils import phapi_lib
except ImportError, e:
    fundamental_libs = False
    logging.debug('Bug filing disabled. %s', e)
else:
    from chromite.lib import cros_build_lib, gdata_lib, gs
    fundamental_libs = True


BUG_CONFIG_SECTION = 'BUG_REPORTING'

CHROMIUM_EMAIL_ADDRESS = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'chromium_email_address', default='')


class Bug(object):
    """Holds the minimum information needed to make a dedupable bug report."""

    def __init__(self, title, summary, search_marker=None, labels=None,
                 owner='', cc=None):
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
        """
        self._title = title
        self._summary = summary
        self._search_marker = search_marker
        self.owner = owner

        self.labels = labels if labels is not None else []
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


class TestFailure(Bug):
    """
    Wrap up all information needed to make an intelligent report about a
    test failure. Each TestFailure has a search marker associated with it
    that can be used to find reports of the same error.
    """

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

    OWNER = global_config.global_config.get_config_value(
            BUG_CONFIG_SECTION, 'test_failure_owner', default='')
    # Number of times to retry if a gs command fails. Defaults to 10,
    # which is far too long given that we already wait on these files
    # before starting HWTests.
    _GS_RETRIES = 1


    _HTTP_ERROR_THRESHOLD = 400

    def __init__(self, build, chrome_version, suite, result):
        """
        @param build: The build type, of the form <board>/<milestone>-<release>.
                      eg: x86-mario-release/R25-4321.0.0
        @param chrome_version: The chrome version associated with the build.
                               eg: 28.0.1498.1
        @param suite: The name of the suite that this test run is a part of.
        @param result: The status of the job associated with this failure.
                       This contains the status, job id, test name, hostname
                       and reason for failure.
        """
        self.build = build
        self.chrome_version = chrome_version
        self.suite = suite
        self.name = result.test_name
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
        self.cc = [self.OWNER]
        self.labels = []

    def title(self):
        """Combines information about this failure into a title string."""
        return '[%s] %s failed on %s' % (self.suite, self.name, self.build)


    def summary(self):
        """Combines information about this failure into a summary string."""

        links = self._get_links_for_failure()
        template = ('This bug has been automatically filed to track the '
                   'following failure:\nTest: %(test)s.\nSuite: %(suite)s.\n'
                   'Chrome Version: %(chrome_version)s.\n'
                   'Build: %(build)s.\n\nReason:\n%(reason)s.\n'
                   'build artifacts: %(build_artifacts)s.\n'
                   'results log: %(results_log)s.\n'
                   'buildbot stages: %(buildbot_stages)s.\n')

        specifics = {
            'test': self.name,
            'suite': self.suite,
            'build': self.build,
            'chrome_version': self.chrome_version,
            'reason': self.reason,
            'build_artifacts': links.artifacts,
            'results_log': links.results,
            'buildbot_stages': links.buildbot,
        }

        return template % specifics


    def search_marker(self):
        """Return an Anchor that we can use to dedupe this exact failure."""
        return "%s(%s,%s,%s)" % ('TestFailure', self.suite,
                                 self.name, self.reason)


    def _link_build_artifacts(self):
        """Returns an url to build artifacts on google storage."""
        return (self._gs_domain + self._arg_prefix +
                self._chromeos_image_archive + self.build)


    def _link_result_logs(self):
        """Returns an url to test logs on google storage."""
        if self.job_id and self.result_owner and self.hostname:
            path_to_object = '%s-%s/%s/%s' % (self.job_id, self.result_owner,
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
        if not fundamental_libs:
            return
        try:
            gs_context = gs.GSContext(retries=self._GS_RETRIES)
            gs_cmd = '%s%s%s/metadata.json' % (self._gs_file_prefix,
                                               self._chromeos_image_archive,
                                               self.build)
            return json.loads(gs_context.Cat(gs_cmd).output)
        except (cros_build_lib.RunCommandError, gs.GSContextException) as e:
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

            return ('%s%s/builds/%s' %
                        (self._buildbot_builders,
                         metadata.get('builder-name'),
                         metadata.get('build-number'))).replace(' ', '%20')
        return 'NA'


    def _get_links_for_failure(self):
        """Returns a named tuple of links related to this failure."""
        links = collections.namedtuple('links', ('results,'
                                                 'artifacts,'
                                                 'buildbot'))
        return links(self._link_result_logs(),
                     self._link_build_artifacts(),
                     self._link_buildbot_stages())


class Reporter(object):
    """
    Files external reports about bugs that happened inside autotest.
    """
    _project_name = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'project_name', default='')
    _username = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'username', default='')
    _password = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'password', default='')

    # Credentials for access to the project hosting api
    _oauth_credentials = global_config.global_config.get_config_value(
        BUG_CONFIG_SECTION, 'credentials', default='')

    _PREDEFINED_LABELS = ['autofiled', 'OS-Chrome',
                          'Type-Bug', 'Restrict-View-Google']

    _LAB_ERROR_TEMPLATE = {
        'labels': ['Bug-Filer-Bug'],
        'owner': TestFailure.OWNER,
        # Set the status to Invalid so we don't dedupe against these bugs.
        'status': 'Invalid',
    }

    _SEARCH_MARKER = 'ANCHOR  '


    def __init__(self):
        if not fundamental_libs:
            logging.warning("Bug filing disabled due to missing imports.")
            return

        try:
            self._phapi_client = phapi_lib.ProjectHostingApiClient(
                self._oauth_credentials,
                self._project_name)

        except phapi_lib.ProjectHostingApiException as e:
            logging.error('Unable to create project hosting api client: %s', e)
            self._phapi_client = None


    def _check_tracker(self):
        """Returns True if we have a tracker object to use for filing bugs."""
        return fundamental_libs and self._phapi_client


    def _get_owner(self, bug):
        """
        Returns an owner for the given bug.

        @param bug: A Bug object for which a bug is about to get filed.
        @return: A string with the email address of the owner of this bug.
                 The issue associated with the bug will get assigned to the
                 owner and they will receive an email from the bug tracker. If
                 there is no obvious owner for the bug an empty string is
                 returned.
        """
        try:
            if bug.lab_error:
                return TestFailure.OWNER
        except AttributeError:
            pass

        return bug.owner


    def _format_issue_options(self, override, **kwargs):
        """
        Override the default issue configuration with a suite specific
        configuration when one is specified in the suite's bug_template.
        The bug_template is specified in the suite control file. After
        overriding the correct options, format them in a way that's understood
        by the project hosting api.

        @param override: Suite specific dictionary with issue config operations.
        @param kwargs: Keyword args containing the default issue config options.
        @return: A dictionary which contains the suite specific options, and the
                 default option when a suite specific option isn't specified.
        """
        if override:
            kwargs.update((k,v) for k,v in override.iteritems() if v)

        kwargs['labels'] = list(set(kwargs['labels'] + self._PREDEFINED_LABELS))
        kwargs['cc'] = list(map(lambda cc: {'name': cc},
                                set(kwargs['cc'] + kwargs['sheriffs'])))

        # The existence of an owner key will cause the api to try and match
        # the value under the key to a member of the project, resulting in a
        # 404 or 500 Http response when the owner is invalid.
        if (CHROMIUM_EMAIL_ADDRESS not in kwargs['owner']):
            del(kwargs['owner'])
        else:
            kwargs['owner'] = {'name': kwargs['owner']}
        return kwargs


    def _anchor_summary(self, bug):
        """
        Creates the summary that can be used for bug deduplication.

        Only attaches the anchor if the search_marker on the bug is not None.

        @param: The bug to create the anchored summary for.

        @return the summary with the anchor appened if the search marker is not
                None, otherwise return the summary.
        """
        if bug.search_marker() is None:
            return bug.summary()
        else:
            return '%s\n\n%s%s\n' % (bug.summary(), self._SEARCH_MARKER,
                                     bug.search_marker())


    def create_bug_report(self, bug, bug_template={}, sheriffs=[]):
        """
        Creates a new bug report.

        @param bug: The Bug instance to create the report for.
        @param bug_template: A template of options to use for filing bugs.
        @param sheriffs: A list of chromium email addresses (of sheriffs)
                         to cc on this bug. Since the list of sheriffs is
                         dynamic it needs to be determined at runtime, as
                         opposed to the normal cc list which is available
                         through the bug template.
        @return: id of the created issue, or None if an issue wasn't created.
                 Note that if either the description or title fields are missing
                 we won't be able to create a bug.
        """
        if not self._check_tracker():
            logging.error("Can't file: %s", title)
            return None

        anchored_summary = self._anchor_summary(bug)

        issue = self._format_issue_options(bug_template, title=bug.title(),
            description=anchored_summary, labels=bug.labels,
            status='Untriaged', owner=self._get_owner(bug), cc=bug.cc,
            sheriffs=sheriffs)

        try:
            filed_bug = self._phapi_client.create_issue(issue)
        except phapi_lib.ProjectHostingApiException as e:
            logging.error('Unable to create a bug for issue with title: %s and '
                          'description %s', bug.title(),
                          anchored_summary)
        else:
            logging.info('Filing new bug %s, with description %s',
                         filed_bug.get('id'), anchored_summary)
            return filed_bug.get('id')


    def _modify_bug_report(self, issue_id, comment=''):
        """
        Modifies an existing bug report with a new comment.

        @param issue_id: Id of the issue to update with.
        @param comment: Comment to update the issue with.
        """
        try:
            self._phapi_client.update_issue(issue_id, {'content': comment})
        except phapi_lib.ProjectHostingApiException as e:
            logging.warning('Unable to add comment %s to existing issue %s: %s',
                            comment, issue_id, e)
        else:
            logging.info('Added comment %s, to issue %s', comment, issue_id)


    def _find_issue_by_marker(self, marker):
        """
        Queries the tracker to find if there is a bug filed for this issue.

        1. 'Escape' the string: cgi.escape is the easiest way to achieve this,
           though it doesn't handle all html escape characters.
           eg: replace '"<' with '&quot;&lt;'
        2. Perform an exact search for the escaped string, if this returns an
           empty issue list perform a more relaxed query and finally fall back
           to a query devoid of the reason field. Between these 3 queries we
           should retrieve the super set of all issues that this marker can be
           in. In most cases the first search should return a result, examples
           where this might not be the case are when the reason field contains
           information that varies between test runs. Since the second search
           has raw escape characters it will match comments too, and the last
           should match all similar issues regardless.
        3. Look through the issues for an exact match between clean versions
           of the marker and summary; for now 'clean' means bereft of numbers.
        4. If no match is found look through a list of comments for each issue.

        @param marker The marker string to search for to find a duplicate of
                     this issue.
        @return A gdata_lib.Issue instance of the issue that was found, or
                None if no issue was found. Also returns None if the marker
                is None.
        """

        if marker is None:
            logging.info('No search marker specified, will create new issue.')
            return None

        # Note that this method cannot handle markers which have already been
        # html escaped, as it will try and unescape them by converting the &
        # to &amp again, thereby failing deduplication.
        marker = HTMLParser.HTMLParser().unescape(marker)
        html_escaped_marker = cgi.escape(marker, quote=True)

        # The tracker frontend stores summaries and comments as html elements,
        # specifically, a summary turns into a span and a comment into
        # preformatted text. Eg:
        # 1. A summary of >& would become <span>&gt;&amp;</span>
        # 2. A comment of >& would become <pre>&gt;&amp;</pre>
        # When searching for exact matches in text, the gdata api gets this
        # feed and parses all <pre> tags unescaping html, then matching your
        # exact string to that. However it does not unescape all <span> tags,
        # presumably for reasons of performance. Therefore a search for the
        # exact string ">&" would match issue 2, but not issue 1, and a search
        # for "&gt;&amp;" would match issue 1 but not issue 2. This problem is
        # further exacerbated when we have quotes within our search string,
        # which is common when the reason field contains a python dictionary.
        #
        # Our searching strategy prioritizes exact matches in the summary, since
        # the first bug thats filed will have a summary with the anchor. If we
        # do not find an exact match in any summary we search through all
        # related issues of the same bug/suite in the hope of finding an exact
        # match in the comments. Note that the comments are returned as
        # unescaped text.
        #
        # TODO(beeps): when we start merging issues this could return bloated
        # results, for now we only search open issues.
        markers = ['"' + self._SEARCH_MARKER + html_escaped_marker + '"',
                   self._SEARCH_MARKER + marker,
                   self._SEARCH_MARKER + ','.join(marker.split(',')[:2])]
        for decorated_marker in markers:
            issues = self._phapi_client.get_tracker_issues_by_text(
                decorated_marker)
            if issues:
                break

        if not issues:
            return

        # Breadth first, since open issues/bugs probably < comments/issue.
        # If we find more than one issue matching a particular anchor assign
        # a mystery bug with all relevent information on the owner and return
        # the first matching issue.
        clean_marker = re.sub('[0-9]+', '', html_escaped_marker)
        all_issues = [issue for issue in issues
                      if clean_marker in re.sub('[0-9]+', '', issue.summary)]

        if len(all_issues) > 1:
            issue_ids = [issue.id for issue in all_issues]
            logging.warning('Multiple results for a specific query. Query: %s, '
                            'results: %s', marker, issue_ids)

        if all_issues:
            return all_issues[0]

        unescaped_clean_marker = re.sub('[0-9]+', '', marker)
        for issue in issues:
            if any(unescaped_clean_marker in re.sub('[0-9]+', '', comment)
                   for comment in issue.comments):
                return issue


    def report(self, bug, bug_template={}):
        """
        Report a bug to the bug tracker. If this bug has already
        happened, post a comment on the existing bug about it occurring again.
        If this is a new bug, create a new bug about it.

        @param bug: A Bug instance about the bug.
        @param bug_template: A template dictionary specifying the default bug
                             filing options for the bug or failures in this
                             suite.

        @return: The issue id of the issue that was either created or modified.
        """
        if not self._check_tracker():
            logging.error("Can't file %s", bug.title())
            return None

        # If our search string sends pythons xml module into a state which it
        # believes will lead to an xml syntax error, it will give up and throw
        # an exception. This might happen with aborted jobs that contain weird
        # escape charactes in their reason fields. We'd rather create a new
        # issue than fail in dedulicating such cases.
        issue = None
        try:
            issue = self._find_issue_by_marker(bug.search_marker())
        except expat.ExpatError as e:
            logging.warning('Unable to deduplicate, creating new issue: %s',
                            str(e))

        if issue:
            comment = '%s\n\n%s' % (bug.title(), self._anchor_summary(bug))
            self._modify_bug_report(issue.id, comment)
            return issue.id

        sheriffs = []

        # TODO(beeps): move this to classify_bug
        try:
            if bug.lab_error:
                if bug_template.get('labels'):
                    self._LAB_ERROR_TEMPLATE['labels'] += bug_template.get(
                                                            'labels')
                bug_template = self._LAB_ERROR_TEMPLATE
            elif bug.suite == 'bvt':
                sheriffs = site_utils.get_sheriffs()
        except AttributeError:
            pass

        return self.create_bug_report(bug, bug_template, sheriffs)
