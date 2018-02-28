# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import utils

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.enterprise import enterprise_policy_base
from autotest_lib.client.cros.input_playback import input_playback

POLL_TIMEOUT = 5
POLL_FREQUENCY = 0.5


class policy_DisableScreenshots(
        enterprise_policy_base.EnterprisePolicyTest):
    version = 1

    def initialize(self, **kwargs):
        """Emulate a keyboard in order to play back the screenshot shortcut."""
        self._initialize_test_constants()
        super(policy_DisableScreenshots, self).initialize(**kwargs)
        self.player = input_playback.InputPlayback()
        self.player.emulate(input_type='keyboard')
        self.player.find_connected_inputs()


    def _initialize_test_constants(self):
        """Initialize test-specific constants, some from class constants."""
        self.POLICY_NAME = 'DisableScreenshots'
        self._DOWNLOADS = '/home/chronos/user/Downloads/'
        self._SCREENSHOT_PATTERN = 'Screenshot*'
        self._SCREENSHOT_FILENAME = self._DOWNLOADS + self._SCREENSHOT_PATTERN

        self.TEST_CASES = {
            'DisableScreenshot_Block': True,
            'False_Allow': False,
            'NotSet_Allow': None
        }

        # JavaScript used to write API results to global CAPTURE variable
        self.CAPTURE_CMDS = [
            ('captureVisibleTab', 'chrome.tabs.captureVisibleTab((img) => '
                                      'CAPTURE = img);'),
            ('tabCapture', 'chrome.tabCapture.capture({video: true}, '
                                '(stream) => CAPTURE = stream);'),
            # TODO(timkovich): https://crbug.com/817497
            # ('desktopCapture', 'chrome.desktopCapture.chooseDesktopMedia( '
            #                         "['screen'], (streamId) => "
            #                         'CAPTURE = streamId);')
        ]


    def _load_extension_page(self):
        """Open options page for screenshot extension."""
        extension = self.cr.get_extension(self._extension_path)
        options_page = ('chrome-extension://%s/options.html' %
                       extension.extension_id)
        self._ext = self.cr._browser.tabs.New()
        self._ext.Navigate(options_page)


    def _screenshot_file_exists(self):
        """
        Checks if screenshot file was created by keyboard shortcut.

        @returns boolean indicating if screenshot file was saved or not.

        """
        try:
            utils.poll_for_condition(
                    lambda: len(glob.glob(self._SCREENSHOT_FILENAME)) > 0,
                    timeout=POLL_TIMEOUT,
                    sleep_interval=POLL_FREQUENCY)
        except utils.TimeoutError:
            logging.info('Screenshot file not found.')
            return False

        logging.info('Screenshot file found.')
        return True


    def _delete_screenshot_files(self):
        """Delete existing screenshot files, if any."""
        for filename in glob.glob(self._SCREENSHOT_FILENAME):
            os.remove(filename)


    def cleanup(self):
        """Cleanup files created in this test, if any and close the player."""
        self._delete_screenshot_files()
        self.player.close()
        super(policy_DisableScreenshots, self).cleanup()


    def _test_screenshot_shortcut(self, policy_value):
        """
        Verify DisableScreenshots is enforced for the screenshot shortcut.

        When DisableScreenshots policy value is undefined, screenshots shall
        be captured via the keyboard shortcut Ctrl + F5.
        When DisableScreenshots policy is set to True screenshots shall not
        be captured.

        @param policy_value: policy value for this case.

        """
        logging.info('Deleting preexisting Screenshot files.')
        self._delete_screenshot_files()

        # Keyboard shortcut for screenshots
        self.player.blocking_playback_of_default_file(
                input_type='keyboard', filename='keyboard_ctrl+f5')

        screenshot_file_captured = self._screenshot_file_exists()
        if policy_value:
            if screenshot_file_captured:
                raise error.TestFail('Screenshot should not be captured')
        elif not screenshot_file_captured:
            raise error.TestFail('Screenshot should be captured')


    def _test_screenshot_apis(self, policy_value):
        """
        Verify DisableScreenshot policy blocks API calls.

        Attempts to capture the screen using all of the methods to capture
        the screen through the APIs. Captures should not happen when
        policy_value is True and should happen in the other cases.

        @param policy_value: policy value for this case

        @raises error.TestFail: In the case where the capture behavior
            does not match the policy value

        """
        self._load_extension_page()

        # Enable activeTab permission for tab by calling extension's shortcut
        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.player.blocking_playback(
                input_type='keyboard',
                filepath=os.path.join(current_dir, 'keyboard_ctrl+shift+y'))

        for method, cmd in self.CAPTURE_CMDS:
            self._ext.ExecuteJavaScript('CAPTURE = null')
            self._ext.ExecuteJavaScript(cmd)

            # desktopCapture opens a prompt window that needs to be OKed
            if method == 'desktopCapture':
                self.player.blocking_playback_of_default_file(
                        input_type='keyboard', filename='keyboard_enter')

            try:
                utils.poll_for_condition(
                        lambda: self._ext.EvaluateJavaScript('CAPTURE != null'),
                        timeout=POLL_TIMEOUT)
                capture = self._ext.EvaluateJavaScript('CAPTURE')
            except utils.TimeoutError:
                capture = None

            if policy_value:
                # tabCapture returns {} on failure, the others return None
                if capture is not None and capture != {}:
                    raise error.TestFail('Screen should not be captured. '
                                         'method = %s' % method)
            elif capture is None:
                raise error.TestFail('Screen should be captured. '
                                     'method = %s' % method)


    def run_once(self, case):
        """
        Setup and run the test configured for the specified test case.

        @param case: Name of the test case to run.

        """
        case_value = self.TEST_CASES[case]
        self._extension_path = os.path.join(os.path.dirname(__file__),
                                            'Screenshooter')

        self.setup_case(user_policies={self.POLICY_NAME: case_value},
                        extension_paths=[self._extension_path])

        self._test_screenshot_shortcut(case_value)
        self._test_screenshot_apis(case_value)
