# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test

class security_BundledExtensions(cros_ui_test.UITest):
    version = 1
    def load_baseline(self):
        bfile = open(os.path.join(self.bindir, 'baseline'))
        with open(os.path.join(self.bindir, 'baseline')) as bfile:
            baseline = []
            for line in bfile:
                if not line.startswith('#'):
                    baseline.append(line)
            baseline = json.loads(''.join(baseline))
        self._ignored_extension_names = baseline['ignored_extension_names']
        self._ignored_crx_files = baseline['ignored_crx_files']
        self._bundled_crx_directory = baseline['bundled_crx_directory']
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
            if not rec['name'] in self._ignored_extension_names:
                filtered_info.append(rec)
        return filtered_info


    def assert_perms_match(self, expected_set, actual_set, perm_type,
                           full_expected_info, full_actual_info):
        """Asserts that the set of permissions for an extension is expected.

        Args:
          expected_set: A set of permissions that are expected to be present.
          actual_set: A set of permissions that are actually present.
          perm_type: A string describing the type of permission involved.
          full_expected_info: A dictionary fully describing the expected
                              information associated with the given extension.
          full_actual_info: A dictionary fully describing the actual
                            information associated with the given extension.
        """
        def _diff_set_msg(expected_set, actual_set):
            strings = []
            for missing_item in expected_set.difference(actual_set):
                strings.append('Missing item: "%s"' % missing_item)
            for extra_item in actual_set.difference(expected_set):
                strings.append('Unexpected (extra) item: "%s"' % extra_item)
            return '\n'.join(strings)

        self.pyauto.assertEqual(
            expected_set, actual_set,
            msg=('%s do not match for "%s".\n'
                 '%s\n'
                 'Expected extension info:\n%s'
                 '\nActual extension info:\n%s' %
                 (perm_type, full_expected_info['name'],
                  _diff_set_msg(expected_set, actual_set),
                  self.pyauto.pformat(full_expected_info),
                  self.pyauto.pformat(full_actual_info))))


    def assert_names_match(self, expected_set, actual_set, ext_type,
                           full_expected_info, full_actual_info):
        """Asserts that a set of extensions is expected.

        Args:
          expected_set: A set of extension names that are expected to be
                        present.
          actual_set: A set of extension names that are actually present.
          ext_type: A string describing the type of extensions involved.
          full_expected_info: A list of dictionaries describing the expected
                              information for all extensions.
          full_actual_info: A list of dictionaries describing the actual
                            information for all extensions.
        """
        def _diff_set_msg(expected_set, actual_set):
            strings = []
            for missing_item in expected_set.difference(actual_set):
                strings.append('Missing item: "%s"' % missing_item)
                located_ext_info = [info for info in full_expected_info if
                                    info['name'] == missing_item][0]
                strings.append(self.pyauto.pformat(located_ext_info))
            for extra_item in actual_set.difference(expected_set):
                strings.append('Unexpected (extra) item: "%s"' % extra_item)
                located_ext_info = [info for info in full_actual_info if
                                    info['name'] == extra_item][0]
                strings.append(self.pyauto.pformat(located_ext_info))
            return '\n'.join(strings)

        self.pyauto.assertEqual(
            expected_set, actual_set,
            msg='%s names do not match the baseline.\n'
                '%s\n' % (ext_type, _diff_set_msg(expected_set, actual_set)))


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
            self.pyauto.InstallExtension(crx_file)
        except pyauto_errors.JSONInterfaceError:
            logging.error('Installation failed for %s' % crx_file)


    def verify_extension_perms(self, baseline):
        """Ensures extension permissions in the baseline match actual info.

        This function will fail the current test if either (1) an
        extension named in the baseline is not currently installed in
        Chrome; or (2) the api permissions or effective host
        permissions of an extension in the baseline do not match the
        actual permissions associated with the extension in Chrome.

        Args:
          baseline: A dictionary of expected extension information, containing
                    extension names and api/effective host permission info.
        """
        full_ext_actual_info = self.get_extensions_info()
        for ext_expected_info in baseline:
            located_ext_info = [info for info in full_ext_actual_info if
                                info['name'] == ext_expected_info['name']]
            self.pyauto.assertTrue(
                located_ext_info,
                msg=('Cannot locate extension info for "%s".\n'
                     'Expected extension info:\n%s' %
                     (ext_expected_info['name'],
                      self.pyauto.pformat(ext_expected_info))))
            ext_actual_info = located_ext_info[0]
            self.assert_perms_match(
                set(ext_expected_info['effective_host_permissions']),
                set(ext_actual_info['effective_host_permissions']),
                'Effective host permissions', ext_expected_info,
                ext_actual_info)
            self.assert_perms_match(
                set(ext_expected_info['api_permissions']),
                set(ext_actual_info['api_permissions']),
                'API permissions', ext_expected_info, ext_actual_info)


    def test_component_extension_permissions(self):
        """Ensures component extension permissions are as expected."""
        expected_names = [ext['name'] for ext in
                          self._component_extension_baseline]
        ext_actual_info = self.get_extensions_info()
        actual_names = [ext['name'] for ext in ext_actual_info if
                        ext['is_component']]
        self.assert_names_match(
            set(expected_names), set(actual_names), 'Component extension',
            self._component_extension_baseline, ext_actual_info)
        self.verify_extension_perms(self._component_extension_baseline)


    def test_bundled_crx_permissions(self):
        """Ensures bundled CRX permissions are as expected."""
        # Verify that each bundled CRX on the device is expected, then
        # install it.
        for file_name in os.listdir(self._bundled_crx_directory):
            if file_name in self._ignored_crx_files:
                logging.debug('Ignoring %s' % file_name)
                continue
            if file_name.endswith('.crx'):
                self.pyauto.assertTrue(
                    file_name in [x['crx_file'] for x in
                                  self._bundled_crx_baseline],
                    msg='Unexpected CRX file: ' + file_name)
                crx_file = os.path.join(self._bundled_crx_directory, file_name)
                self.attempt_install(crx_file)

        # Verify that the permissions information in the baseline matches the
        # permissions associated with the installed bundled CRX extensions.
        self.verify_extension_perms(self._bundled_crx_baseline)


    def test_no_unexpected_extensions(self):
        """Ensures there are no unexpected bundled or component extensions."""
        # Install all bundled extensions on the device.
        for file_name in os.listdir(self._bundled_crx_directory):
            if file_name in self._ignored_crx_files:
                logging.debug('Ignoring %s' % file_name)
                continue
            if file_name.endswith('.crx'):
                crx_file = os.path.join(self._bundled_crx_directory, file_name)
                self.attempt_install(crx_file)
        logging.debug('Done installing extensions')

        # Ensure that the set of installed extension names precisely
        # matches the baseline.
        expected_names = [ext['name'] for ext in
                          self._component_extension_baseline]
        expected_names.extend([ext['name'] for ext in
                               self._bundled_crx_baseline])
        ext_actual_info = self.get_extensions_info()
        installed_names = [ext['name'] for ext in ext_actual_info]
        self.assert_names_match(
            set(expected_names), set(installed_names), 'Installed extension',
            self._component_extension_baseline + self._bundled_crx_baseline,
            ext_actual_info)


    def run_once(self, mode=None):
        self.load_baseline()
        if self.pyauto.GetBrowserInfo()['properties']['is_official']:
            self._component_extension_baseline.extend(self._official_components)

        # In pyauto this was implemented as 3 different tests, each of
        # which can raise without stopping execution of the other two,
        # and each of which was run in its own clean session.
        # The autotest analogue is to label these in the control file as
        # 3 distinct runs of the test.
        if mode == 'ComponentExtensionPermissions':
            self.test_component_extension_permissions()
        elif mode == 'BundledCrxPermissions':
            self.test_bundled_crx_permissions()
        elif mode == 'NoUnexpectedExtensions':
            self.test_no_unexpected_extensions()
        else:
            error.TestFail('Unimplemented: %s' % mode)
