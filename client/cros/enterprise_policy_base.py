# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import cryptohome
from autotest_lib.client.cros import enterprise_base

ENTERPRISE_STAGING_FLAGS = [
    '--gaia-url=https://gaiastaging.corp.google.com',
    '--lso-url=https://test-sandbox.auth.corp.google.com',
    '--google-apis-url=https://www-googleapis-test.sandbox.google.com',
    '--oauth2-client-id=236834563817.apps.googleusercontent.com',
    '--oauth2-client-secret=RsKv5AwFKSzNgE0yjnurkPVI',
    ('--cloud-print-url='
     'https://cloudprint-nightly-ps.sandbox.google.com/cloudprint'),
    '--ignore-urlfetcher-cert-requests']
ENTERPRISE_TESTDMS_FLAGS = [
    '--ignore-urlfetcher-cert-requests',
    '--enterprise-enrollment-skip-robot-auth',
    '--disable-policy-key-verification']
ENTERPRISE_FLAGS_DICT = {
    'prod': [],
    'cr-dev': ENTERPRISE_STAGING_FLAGS,
    'cr-auto': ENTERPRISE_STAGING_FLAGS,
    'dm-test': ENTERPRISE_TESTDMS_FLAGS,
    'dm-fake': ENTERPRISE_TESTDMS_FLAGS
}
ENTERPRISE_DMS_URL_DICT = {
    'prod': 'http://m.google.com/devicemanagement/data/api',
    'cr-dev': 'https://cros-dev.sandbox.google.com/devicemanagement/data/api',
    'cr-auto': 'https://cros-auto.sandbox.google.com/devicemanagement/data/api',
    'dm-test': 'http://chromium-dm-test.appspot.com/d/%s',
    'dm-fake': 'http://127.0.0.1:%d/'
}
ENTERPRISE_DMSERVER = '--device-management-url=%s'


class EnterprisePolicyTest(enterprise_base.EnterpriseTest):
    """Base class for Enterprise Policy Tests."""

    def setup(self):
        os.chdir(self.srcdir)
        utils.make()

    def initialize(self, args=[]):
        self._initialize_test_context(args)

        # Start AutoTest DM Server if using local fake server.
        if self.env == 'dm-fake':
            self.import_dmserver(self.srcdir)
            self.start_dmserver()
        self._initialize_chrome_extra_flags()

    def cleanup(self):
        # Clean up AutoTest DM Server if using local fake server.
        if self.env == 'dm-fake':
            super(EnterprisePolicyTest, self).cleanup()

        # Close Chrome instance if opened.
        if self.cr:
            self.cr.close()

    def _initialize_test_context(self, args=[]):
        """Initializes class-level test context parameters."""
        # Extract local parameters from command line args.
        args_dict = utils.args_to_dict(args)
        self.mode = args_dict.get('mode', 'all')
        self.case = args_dict.get('case')
        self.env = args_dict.get('env', 'dm-fake')
        self.value = args_dict.get('value')
        self.username = args_dict.get('username')
        self.password = args_dict.get('password')
        self.dms_name = args_dict.get('dms_name')

        # Verify |case| is given iff |mode|==single.
        if self.mode == 'single' and not self.case:
            raise error.TestError('case must be given when running '
                                  'in single mode.')
        if self.mode != 'single' and self.case:
            raise error.TestError('case must not be given when not running '
                                  'in single mode.')

        # Verify |env| is valid.
        if self.env not in ENTERPRISE_FLAGS_DICT:
            raise error.TestError('env=%s is invalid.' % self.env)

        # Verify |value| is not given when the |env| is 'dm-fake' or
        # a test |case| is not specified.
        if self.value is not None:
            if self.env == 'dm-fake' or self.case is None:
                raise error.TestError('value must not be given when using the '
                                      'fake DM Server or without a specific '
                                      'test case.')

        # Verify |dms_name| is given iff |env|==dm-test.
        if self.env == 'dm-test' and not self.dms_name:
            raise error.TestError('dms_name must be given when using '
                                  'env=dm-test.')
        if self.env != 'dm-test' and self.dms_name:
            raise error.TestError('dms_name must not be given when not using '
                                  'env=dm-test.')

        # Use default value, username, and password with dm-fake.
        if self.env == 'dm-fake':
            self.value = None
            self.username = self.USERNAME
            self.password = self.PASSWORD

        # Log the test context parameters.
        logging.info('Test Context Parameters:')
        logging.info('  Run Mode: %r', self.mode)
        logging.info('  Test Case: %r', self.case)
        logging.info('  Environment: %r', self.env)
        logging.info('  Value Shown: %r', self.value)
        logging.info('  Username: %r', self.username)
        logging.info('  Password: %r', self.password)
        logging.info('  Test DMS Name: %r', self.dms_name)

    def _initialize_chrome_extra_flags(self):
        """Initializes flags used to create Chrome instance."""
        # Construct DM Server URL flags.
        env_flag_list = []
        if self.env != 'prod':
            if self.env == 'dm-fake':
                # Use URL provided by AutoTest DM server.
                dmserver_str = (ENTERPRISE_DMSERVER % self.dm_server_url)
            else:
                # Use URL defined in DMS URL dictionary.
                dmserver_str = (ENTERPRISE_DMSERVER %
                                (ENTERPRISE_DMS_URL_DICT[self.env]))
                if self.env == 'dm-test':
                    dmserver_str = (dmserver_str % self.dms_name)

            # Merge with other flags needed by non-prod enviornment.
            env_flag_list = ([dmserver_str] +
                             ENTERPRISE_FLAGS_DICT[self.env])

        self.extra_flags = env_flag_list
        self.cr = None

    def setup_case(self, policy_name, policy_value, policy_json):
        """Sets up context variables unique to the test case.

        @param policy_name: Name of the policy under test.
        @param policy_value: Expected value shown on chrome://policy page.
        @param policy_json: Json string to set up the fake DMS policy value.
        """
        # Set up policy blob for AutoTest DM Server only if initialized.
        if self.env == 'dm-fake':
            self._setup_policy(policy_json)

        # Launch Chrome browser.
        logging.info('Chrome Browser Arguments:')
        logging.info('  extra_browser_args: %s', self.extra_flags)
        logging.info('  gaia_login: %s', True)
        logging.info('  disable_gaia_services: %s', False)
        logging.info('  autotest_ext: %s', True)
        logging.info('  username: %s', self.username)
        logging.info('  password: %s', self.password)

        self.cr = chrome.Chrome(extra_browser_args=self.extra_flags,
                                gaia_login=True,
                                disable_gaia_services=False,
                                autotest_ext=True,
                                username=self.username,
                                password=self.password)

        # Open a tab to the chrome://policy page.
        self.cr.browser.tabs[0].Activate()
        policy_tab = self.cr.browser.tabs.New()
        policy_tab.Activate()
        policy_tab.Navigate('chrome://policy')
        policy_tab.WaitForDocumentReadyStateToBeComplete()

        # Confirm preconditions of test: user signed in, and policy set.
        # Verify that user's cryptohome directory is mounted.
        if not cryptohome.is_vault_mounted(user=self.username,
                                           allow_fail=True):
            raise error.TestError('Expected to find a mounted vault for %s.'
                                  % self.username)

        # Verify that policy name & value are shown on the Policies page.
        value_shown = self._get_policy_value_shown(policy_tab, policy_name)
        if value_shown != policy_value:
            raise error.TestFail('Policy value shown is not correct: %s '
                                 '(expected: %s)' %
                                 (value_shown, policy_value))

        # Close the Policies tab.
        policy_tab.Close()

    def _setup_policy(self, policy_json):
        """Creates policy blob from JSON data, and sends to AutoTest fake DMS.

        @param policy_json: The policy JSON data (name-value pairs).
        """
        policy_json = self._move_modeless_to_mandatory(policy_json)
        policy_json = self._remove_null_policies(policy_json)

        policy_blob = """{
            "google/chromeos/user": %s,
            "managed_users": ["*"],
            "policy_user": "%s",
            "current_key_index": 0,
            "invalidation_source": 16,
            "invalidation_name": "test_policy"
        }""" % (json.dumps(policy_json), self.USERNAME)
        self.setup_policy(policy_blob)

    def _move_modeless_to_mandatory(self, policy_json):
        """Adds the 'mandatory' mode if a policy's mode was omitted.

        The AutoTest fake DM Server requires that every policy be contained
        within either a 'mandatory' or 'recommended' dictionary, to indicate
        the mode of the policy. This function moves modeless polices into the
        'mandatory' dictionary.

        @param policy_json: The policy JSON data (name-value pairs).
        @returns: dict of policies grouped by mode keys.
        """
        mandatory_policies = {}
        recommended_policies = {}
        collated_json = {}

        # Extract mandatory and recommended policies.
        if 'mandatory' in policy_json:
            mandatory_policies = policy_json['mandatory']
            del policy_json['mandatory']
        if 'recommended' in policy_json:
            recommended_policies = policy_json['recommended']
            del policy_json['recommended']

        # Move remaining modeless policies into mandatory dict.
        if policy_json:
            mandatory_policies.update(policy_json)

        # Collate all policies into mandatory & recommended dicts.
        if recommended_policies:
            collated_json.update({'recommended': recommended_policies})
        if mandatory_policies:
            collated_json.update({'mandatory': mandatory_policies})

        return collated_json

    def _remove_null_policies(self, policy_json):
        """Removes policy dict data that is set to None or ''.

        For the status of a policy to be shown as "Not set" on the
        chrome://policy page, the policy blob must contain no dictionary entry
        for that policy. This function removes policy NVPs from a copy of the
        |policy_json| dictionary that the test case set to None or ''.

        @param policy_json: setup policy JSON data (name-value pairs).
        @returns: setup policy JSON data with all 'Not set' policies removed.
        """
        policy_json_copy = policy_json.copy()
        for mode, policies in policy_json_copy.items():
            for policy_data in policies.items():
                if policy_data[1] is None or policy_data[1] == '':
                    policies.pop(policy_data[0])
        return policy_json_copy

    def _get_policy_value_shown(self, policy_tab, policy_name):
        """Gets the value shown for the named policy on the Policies page.

        Takes |policy_name| as a parameter and returns the corresponding
        policy value shown on the chrome://policy page.

        @param policy_tab: Tab displaying the chrome://policy page.
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

