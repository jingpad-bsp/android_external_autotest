# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import cryptohome
from autotest_lib.client.cros import httpd
from autotest_lib.client.cros import enterprise_fake_dmserver

CROSQA_FLAGS = [
    '--gaia-url=https://gaiastaging.corp.google.com',
    '--lso-url=https://gaiastaging.corp.google.com',
    '--google-apis-url=https://www-googleapis-test.sandbox.google.com',
    '--oauth2-client-id=236834563817.apps.googleusercontent.com',
    '--oauth2-client-secret=RsKv5AwFKSzNgE0yjnurkPVI',
    ('--cloud-print-url='
     'https://cloudprint-nightly-ps.sandbox.google.com/cloudprint'),
    '--ignore-urlfetcher-cert-requests']
CROSALPHA_FLAGS = [
    ('--cloud-print-url='
     'https://cloudprint-nightly-ps.sandbox.google.com/cloudprint'),
    '--ignore-urlfetcher-cert-requests']
TESTDMS_FLAGS = [
    '--ignore-urlfetcher-cert-requests',
    '--disable-policy-key-verification']
FLAGS_DICT = {
    'prod': [],
    'crosman-qa': CROSQA_FLAGS,
    'crosman-alpha': CROSALPHA_FLAGS,
    'dm-test': TESTDMS_FLAGS,
    'dm-fake': TESTDMS_FLAGS
}
DMS_URL_DICT = {
    'prod': 'http://m.google.com/devicemanagement/data/api',
    'crosman-qa':
        'https://crosman-qa.sandbox.google.com/devicemanagement/data/api',
    'crosman-alpha':
        'https://crosman-alpha.sandbox.google.com/devicemanagement/data/api',
    'dm-test': 'http://chromium-dm-test.appspot.com/d/%s',
    'dm-fake': 'http://127.0.0.1:%d/'
}
DMSERVER = '--device-management-url=%s'
# Username and password for the fake dm server can be anything
# they are not used to authenticate against GAIA.
USERNAME = 'fake-user@managedchrome.com'
PASSWORD = 'fakepassword'


class EnterprisePolicyTest(test.test):
    """Base class for Enterprise Policy Tests."""

    def setup(self):
        os.chdir(self.srcdir)
        utils.make()

    def initialize(self, case=None, env='dm-fake', dms_name=None,
                   username=USERNAME, password=PASSWORD):
        """Initialize test parameters, fake DM Server, and Chrome flags.

        @param case: String name of the test case to run.
        @param env: String environment of DMS and Gaia servers.
        @param username: String user name login credential.
        @param password: String password login credential.
        @param dms_name: String name of test DM Server.

        """
        self.case = case
        self.env = env
        self.username = username
        self.password = password
        self.dms_name = dms_name
        self._initialize_context()

        # Start AutoTest DM Server if using local fake server.
        if self.dms_is_fake:
            self.fake_dm_server = enterprise_fake_dmserver.FakeDMServer(
                self.srcdir)
            self.fake_dm_server.start(self.tmpdir, self.debugdir)
        self._initialize_chrome_extra_flags()
        self._web_server = None

    def cleanup(self):
        # Clean up AutoTest DM Server if using local fake server.
        if self.dms_is_fake:
            self.fake_dm_server.stop()

        # Stop web server if it was started.
        if self._web_server:
            self._web_server.stop()

        # Close Chrome instance if opened.
        if self.cr:
            self.cr.close()

    def start_webserver(self, port):
        """Set up an HTTP Server on |port| to serve pages from localhost.

        @param port: Port used by HTTP server.

        """
        self._web_server = httpd.HTTPListener(port, docroot=self.bindir)
        self._web_server.run()

    def _initialize_context(self):
        """Initialize class-level test context parameters.

        @raises error.TestError if context parameter has an invalid value,
                or a combination of parameters have incompatible values.

        """
        # Verify |case| was given. List test case names if not.
        if self.case is None:
            raise error.TestError('Must give a test case: %s' %
                                  ', '.join(self.TEST_CASES))

        # Verify |case| is defined in test class.
        if self.case not in self.TEST_CASES:
            raise error.TestError('Test case is invalid: %s' % self.case)

        # Verify |env| is a valid environment.
        if self.env not in FLAGS_DICT:
            raise error.TestError('Environment is invalid: %s' % self.env)

        # If the fake DM Server will be used, set |dms_is_fake| true.
        self.dms_is_fake = (self.env == 'dm-fake')

        # Verify test |dms_name| is given iff |env| is 'dm-test'.
        if self.env == 'dm-test' and not self.dms_name:
            raise error.TestError('dms_name must be given when using '
                                  'env=dm-test.')
        if self.env != 'dm-test' and self.dms_name:
            raise error.TestError('dms_name must not be given when not using '
                                  'env=dm-test.')

        # Log the test context parameters.
        logging.info('Test Context Parameters:')
        logging.info('  Case: %r', self.case)
        logging.info('  Environment: %r', self.env)
        logging.info('  Username: %r', self.username)
        logging.info('  Password: %r', self.password)
        logging.info('  Test DMS Name: %r', self.dms_name)

    def _initialize_chrome_extra_flags(self):
        """Initialize flags used to create Chrome instance."""
        # Construct DM Server URL flags if not using production server.
        env_flag_list = []
        if self.env != 'prod':
            if self.dms_is_fake:
                # Use URL provided by the fake AutoTest DM server.
                dmserver_str = (DMSERVER % self.fake_dm_server.server_url)
            else:
                # Use URL defined in the DMS URL dictionary.
                dmserver_str = (DMSERVER % (DMS_URL_DICT[self.env]))
                if self.env == 'dm-test':
                    dmserver_str = (dmserver_str % self.dms_name)

            # Merge with other flags needed by non-prod enviornment.
            env_flag_list = ([dmserver_str] + FLAGS_DICT[self.env])

        self.extra_flags = env_flag_list
        self.cr = None

    def setup_case(self, policy_name, policy_value, policies_dict):
        """Set up and confirm the preconditions of a test case.

        If the AutoTest fake DM Server is used, make a JSON policy blob
        from |policies_dict|, and upload it to the fake DM server.

        Launch Chrome and sign in to Chrome OS. Examine the user's
        cryptohome vault, to confirm user is signed in successfully.

        Open the Policies page, and confirm that it shows the specified
        |policy_name| and has the correct |policy_value|.

        @param policy_name: Name of the policy under test.
        @param policy_value: Expected value to appear on chrome://policy page.
        @param policies_dict: Policy dictionary data for fake DM server.

        @raises error.TestError if cryptohome vault is not mounted for user.
        @raises error.TestFail if |policy_name| and |policy_value| are not
                shown on the Policies page.

        """
        if self.dms_is_fake:
            self.fake_dm_server.setup_policy(self._make_json_blob(
                policies_dict))

        self._launch_chrome_browser()
        tab = self.navigate_to_url('chrome://policy')
        if not cryptohome.is_vault_mounted(user=self.username,
                                           allow_fail=True):
            raise error.TestError('Expected to find a mounted vault for %s.'
                                  % self.username)
        value_shown = self._get_policy_value_shown(tab, policy_name)
        if not self._policy_value_matches_shown(policy_value, value_shown):
            raise error.TestFail('Policy value shown is not correct: %s '
                                 '(expected: %s)' %
                                 (value_shown, policy_value))
        tab.Close()

    def _launch_chrome_browser(self):
        """Launch Chrome browser and sign in."""
        logging.info('Chrome Browser Arguments:')
        logging.info('  extra_browser_args: %s', self.extra_flags)
        logging.info('  username: %s', self.username)
        logging.info('  password: %s', self.password)
        logging.info('  gaia_login: %s', not self.dms_is_fake)

        self.cr = chrome.Chrome(extra_browser_args=self.extra_flags,
                                username=self.username,
                                password=self.password,
                                gaia_login=not self.dms_is_fake,
                                disable_gaia_services=False,
                                autotest_ext=True)

    def navigate_to_url(self, url, tab=None):
        """Navigate tab to the specified |url|. Create new tab if none given.

        @param url: URL of web page to load.
        @param tab: browser tab to load (if any).
        @returns: browser tab loaded with web page.

        """
        logging.info('Navigating to URL: %r', url)
        if not tab:
            tab = self.cr.browser.tabs.New()
            tab.Activate()
        tab.Navigate(url, timeout=5)
        tab.WaitForDocumentReadyStateToBeComplete()
        return tab

    def _policy_value_matches_shown(self, policy_value, value_shown):
        """Compare |policy_value| to |value_shown| with whitespace removed.

        Compare the expected policy value with the value actually shown on the
        chrome://policy page. Before comparing, convert both values to JSON
        formatted strings, and remove all whitespace. Whitespace must be
        removed before comparison because Chrome processes some policy values
        to show them in a more human readable format.

        @param policy_value: Expected value to appear on chrome://policy page.
        @param value_shown: Value as it appears on chrome://policy page.
        @param policies_dict: Policy dictionary data for the fake DM server.

        @returns: True if the strings match after removing all whitespace.

        """
        # Convert Python None or '' to JSON formatted 'null' string.
        if value_shown is None or value_shown == '':
            value_shown = 'null'
        if policy_value is None or policy_value == '':
            policy_value = 'null'

        # Remove whitespace.
        trimmed_value = ''.join(policy_value.split())
        trimmed_shown = ''.join(value_shown.split())
        logging.info('Trimmed policy value shown: %r (expected: %r)',
                     trimmed_shown, trimmed_value)
        return trimmed_value == trimmed_shown

    def _make_json_blob(self, policies_dict):
        """Create JSON policy blob from |policies_dict| object.

        @param policies_dict: policies dictionary object.
        @returns: JSON policy blob to send to the fake DM server.

        """
        policies_dict = self._move_modeless_to_mandatory(policies_dict)
        policies_dict = self._remove_null_policies(policies_dict)

        policy_blob = """{
            "google/chromeos/user": %s,
            "managed_users": ["*"],
            "policy_user": "%s",
            "current_key_index": 0,
            "invalidation_source": 16,
            "invalidation_name": "test_policy"
        }""" % (json.dumps(policies_dict), self.username)
        return policy_blob

    def _move_modeless_to_mandatory(self, policies_dict):
        """Add the 'mandatory' mode to each policy where mode was omitted.

        The AutoTest fake DM Server requires that every policy be contained
        within either a 'mandatory' or 'recommended' dictionary, to indicate
        the mode of the policy. This function moves modeless policies into
        the 'mandatory' dictionary.

        @param policies_dict: policy dictionary data.
        @returns: dict of policies grouped by mode keys.

        """
        mandatory_policies = {}
        recommended_policies = {}
        collated_dict = {}

        # Extract mandatory and recommended mode dicts.
        if 'mandatory' in policies_dict:
            mandatory_policies = policies_dict['mandatory']
            del policies_dict['mandatory']
        if 'recommended' in policies_dict:
            recommended_policies = policies_dict['recommended']
            del policies_dict['recommended']

        # Move any remaining modeless policies into mandatory dict.
        if policies_dict:
            mandatory_policies.update(policies_dict)

        # Collate all policies into mandatory & recommended dicts.
        if recommended_policies:
            collated_dict.update({'recommended': recommended_policies})
        if mandatory_policies:
            collated_dict.update({'mandatory': mandatory_policies})

        return collated_dict

    def _remove_null_policies(self, policies_dict):
        """Remove policy NVPs whose value is set to None or ''.

        For the status of a policy to be shown as "Not set" on the
        chrome://policy page, the policy dictionary must contain no NVP for
        for that policy. This function removes policy NVPs from a copy of the
        |policies_dict| dictionary that the test case has set to None or ''.

        @param policies_dict: policy dictionary data.
        @returns: policy dictionary data with all 'Not set' policies removed.

        """
        policies_dict_copy = policies_dict.copy()
        for policies in policies_dict_copy.values():
            for policy_data in policies.items():
                if policy_data[1] is None or policy_data[1] == '':
                    policies.pop(policy_data[0])
        return policies_dict_copy

    def _get_policy_value_shown(self, policy_tab, policy_name):
        """Get the value shown for |policy_name| from the |policy_tab| page.

        Return the policy value for the policy given by |policy_name|, from
        from the chrome://policy page given by |policy_tab|.

        @param policy_tab: Tab displaying the Policies page.
        @param policy_name: The name of the policy.
        @returns: The value shown for the policy on the Policies page.

        """
        row_values = policy_tab.EvaluateJavaScript('''
            var section = document.getElementsByClassName("policy-table-section")[0];
            var table = section.getElementsByTagName('table')[0];
            rowValues = '';
            for (var i = 1, row; row = table.rows[i]; i++) {
               if (row.className !== 'expanded-value-container') {
                  var name_div = row.getElementsByClassName('name elide')[0];
                  var name = name_div.textContent;
                  if (name === '%s') {
                     var value_span = row.getElementsByClassName('value')[0];
                     var value = value_span.textContent;
                     var status_div = row.getElementsByClassName('status elide')[0];
                     var status = status_div.textContent;
                     rowValues = [name, value, status];
                     break;
                  }
               }
            }
            rowValues;
        ''' % policy_name)

        value_shown = row_values[1].encode('ascii', 'ignore')
        status_shown = row_values[2].encode('ascii', 'ignore')
        if status_shown == 'Not set.':
            return None
        return value_shown

    def _get_policy_value_from_new_tab(self, policy_name):
        """Get the policy value for |policy_name| from the Policies page.

        @param policy_name: string of policy name.

        @returns: (string) value of the policy as shown on chrome://policy.

        """
        tab = self.navigate_to_url('chrome://policy')
        value = self._get_policy_value_shown(tab, policy_name)
        tab.Close()

        return value

    def get_elements_from_page(self, tab, cmd):
        """Get collection of page elements that match the |cmd| filter.

        @param tab: tab containing the page to be scraped.
        @param cmd: JavaScript command to evaluate on the page.
        @returns object containing elements on page that match the cmd.
        @raises: TestFail if matching elements are not found on the page.

        """
        try:
            elements = tab.EvaluateJavaScript(cmd)
        except Exception as err:
            raise error.TestFail('Unable to find matching elements on '
                                 'the test page: %s\n %r' %(tab.url, err))
        return elements

    def packed_json_string(self, policy_value):
        """Convert |policy_value| to JSON format string with no whitespace.

        @param policy_value: object containing a policy value.
        @returns: string in JSON format, stripped of whitespace.

        """
        return ''.join(json.dumps(policy_value))

    def _get_policy_data_for_case(self, case):
        """Get policy value and policies dict data for specified test |case|.

        Set expected |policy_value| string and |policies_dict| data to the
        values defined for the specified test |case|. If the value specified
        for the |case| is None, then set |policy_value| to None. Note that
        |policy_value| will be correct only for those policies where
        |policy_dict| contains a list of things (strings, dictionaries, etc).

        @param case: Name of the test case to run.
        @returns: policy_value string and policies_dict data.

        """
        policy_value = None
        if self.TEST_CASES[case]:
            policy_value = ','.join(self.TEST_CASES[case])
        policy_dict = {self.POLICY_NAME: self.TEST_CASES[case]}
        policies_dict = self.SUPPORTING_POLICIES.copy()
        policies_dict.update(policy_dict)
        return policy_value, policies_dict

    def run_once(self):
        """The run_once() method is required by all AutoTest tests.

        run_once() is defined herein to automatically determine which test
        case in the test class to run. The test class must have a public
        run_test_case() method defined. Note: The test class may override
        run_once() if it determines which test case to run.

        """
        logging.info('Running test case: %s', self.case)
        self.run_test_case(self.case)
