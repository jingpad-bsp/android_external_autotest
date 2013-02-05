# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_utils
from autotest_lib.client.cros import cros_ui_test

class security_BundledExtensions(cros_ui_test.UITest):
    version = 2

    def load_baseline(self):
        bfile = open(os.path.join(self.bindir, 'baseline'))
        with open(os.path.join(self.bindir, 'baseline')) as bfile:
            baseline = []
            for line in bfile:
                if not line.startswith('#'):
                    baseline.append(line)
            baseline = json.loads(''.join(baseline))
        self._ignored_extension_ids = baseline['ignored_extension_ids']
        self._bundled_crx_baseline = baseline['bundled_crx_baseline']
        self._component_extension_baseline = baseline[
            'component_extension_baseline']
        self._official_components = baseline['official_components']


    def get_extensions_info(self):
        """Wraps the pyauto method GetExtensionsInfo().

        Filters out extensions that are on the to-be-ignored list.

        Returns:
          A list of dicts, each representing an extension. For more
          information, see the pyauto documentation.
        """
        complete_info = self.pyauto.GetExtensionsInfo()
        logging.debug("GetExtensionsInfo:\n%s" %
                      self.pyauto.pformat(complete_info))
        filtered_info = []
        for rec in complete_info:
            if not rec['id'] in self._ignored_extension_ids:
                filtered_info.append(rec)
        return filtered_info


    def attempt_install(self, crx_file):
        """Try to install a crx, and log an error if it fails.

        Args:
          crx_file: A string containing the path to a .crx file.
        """
        # This helps limit the degree to which future bugs like
        # crbug.com/131480 interfere with testing. The test will still
        # fail, but at least the test will complete (and notice any
        # problems in any *other* extensions).
        import pyauto_errors
        logging.debug('Installing %s' % crx_file)
        try:
            self.pyauto.InstallExtension(crx_file, from_webstore=True)
        except pyauto_errors.JSONInterfaceError:
            logging.error('Installation failed for %s' % crx_file)


    def install_all(self, crx_dirs):
        for crx_dir in crx_dirs:
            if not os.path.exists(crx_dir):
                continue
            for file_name in os.listdir(crx_dir):
                if not file_name.endswith('.crx'):
                    continue
                crx_id = self.crx_id_from_filename(file_name)
                if crx_id in self._ignored_extension_ids:
                    logging.debug('Ignoring %s' % file_name)
                    continue
                self.attempt_install(os.path.join(crx_dir, file_name))
        logging.debug('Done installing extensions')


    def crx_id_from_filename(self, filename):
        return filename.split('.crx')[0]


    def install_and_compare(self):
        test_fail = False
        # Install all bundled extensions on the device.
        main_crx_dir = '/opt/google/chrome/extensions'
        board_specific_crx_dir = '/usr/share/google-chrome/extensions'
        self.install_all([main_crx_dir, board_specific_crx_dir])

        # * Find the set of expected IDs.
        # * Find the set of observed IDs.
        # * Do set comparison to find the unexpected, and the expected/missing.
        combined_baseline = (self._bundled_crx_baseline +
                             self._component_extension_baseline)
        # Filter out any baseline entries that don't apply to this board.
        # If there is no 'boards' limiter on a given record, the record applies.
        # If there IS a 'boards' limiter, check that it applies.
        board = site_utils.get_current_board()
        combined_baseline = [x for x in combined_baseline
                             if ((not 'boards' in x) or
                                 ('boards' in x and board in x['boards']))]

        observed_extensions = self.get_extensions_info()
        observed_ids = set([x['id'] for x in observed_extensions])
        expected_ids = set([x['id'] for x in combined_baseline])

        missing_ids = expected_ids - observed_ids
        missing_names = ['%s (%s)' % (x['name'], x['id'])
                         for x in combined_baseline if x['id'] in missing_ids]

        unexpected_ids = observed_ids - expected_ids
        unexpected_names = ['%s (%s)' % (x['name'], x['id'])
                            for x in observed_extensions if
                            x['id'] in unexpected_ids]

        good_ids = expected_ids.intersection(observed_ids)

        if missing_names:
            logging.error('Missing: %s' % '; '.join(missing_names))
            test_fail = True
        if unexpected_names:
            logging.error('Unexpected: %s' % '; '.join(unexpected_names))
            test_fail = True

        # For those IDs in both the expected-and-observed, ie, "good":
        #   Compare sets of expected-vs-actual API permissions, report diffs.
        #   Do same for host permissions.
        for good_id in good_ids:
            baseline = [x for x in combined_baseline if x['id'] == good_id][0]
            actual = [x for x in observed_extensions if x['id'] == good_id][0]
            # Check the API permissions.
            baseline_apis = set(baseline['api_permissions'])
            actual_apis = set(actual['api_permissions'])
            missing_apis = baseline_apis - actual_apis
            unexpected_apis = actual_apis - baseline_apis
            if missing_apis or unexpected_apis:
                test_fail = True
                self._report_attribute_diffs(missing_apis, unexpected_apis,
                                             actual)
            # Check the host permissions.
            baseline_hosts = set(baseline['effective_host_permissions'])
            actual_hosts = set(actual['effective_host_permissions'])
            missing_hosts = baseline_hosts - actual_hosts
            unexpected_hosts = actual_hosts - baseline_hosts
            if missing_hosts or unexpected_hosts:
                test_fail = True
                self._report_attribute_diffs(missing_hosts, unexpected_hosts,
                                             actual)
        if test_fail:
            raise error.TestFail('Bundled extensions mismatch, see error log.')


    def _report_attribute_diffs(self, missing, unexpected, rec):
        logging.error('Problem with %s (%s):' % (rec['name'], rec['id']))
        if missing:
            logging.error('It no longer uses: %s' % '; '.join(missing))
        if unexpected:
            logging.error('It unexpectedly uses: %s' % '; '.join(unexpected))


    def run_once(self, mode=None):
        self.load_baseline()
        if self.pyauto.GetBrowserInfo()['properties']['is_official']:
            self._component_extension_baseline.extend(self._official_components)

        self.install_and_compare()
