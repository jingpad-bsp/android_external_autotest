# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import httpd


class video_YouTubeMseEme(test.test):
    """The main test class for MSE/EME.

    """


    version = 1

    PLAYER_PAGE = 'http://localhost:8000/video_YouTubeMseEme.html'
    TEST_JS = 'files/video_YouTubeMseEme.js'

    POLLING_TIME = 0.1


    def init(self, chrome, player_page):
        """Initialization function for this test class.

        @param chrome: An Autotest Chrome instance.
        @param player_page: Dummy HTML file to load.

        """
        self._testServer = httpd.HTTPListener(
                8000, docroot=os.path.join(os.path.dirname(__file__), 'files'))
        self._testServer.run()

        self.tab = chrome.browser.tabs[0]
        self.tab.Navigate(player_page)
        self.tab.WaitForDocumentReadyStateToBeComplete()
        self.load_javascript(self.TEST_JS)


    def check_event_happened(self, event, delay_time_sec=2):
        """A wrapper to check if an event in JS has fired.

        @param event: A string to denote the event to check.
        @param delay_time_sec: Time to wait before querying the test (float).
                This is to give the VM some time to schedule the next execution.

        @returns: A boolean indicating if the event has fired.

        """
        start_time = time.time()
        while time.time() - start_time <= delay_time_sec:
            if self.tab.EvaluateJavaScript(
                    'window.__eventReporter["%s"] === true;' % event):
                return True
            time.sleep(self.POLLING_TIME)
        return False


    def load_javascript(self, sub_path):
        """A wrapper to load a JS file into the current tab.

        @param sub_path: The relative path from the current .py file.

        """
        full_path = os.path.join(os.path.dirname(__file__), sub_path)
        with open(full_path) as f:
            js = f.read()
            self.tab.ExecuteJavaScript(js)
            logging.info('Loaded accompanying .js script.')


    def get_test_state(self, test_name, delay_time_sec=2):
        """A wrapper to check the state of a test in the accompanying JS.

        @param test_name: The name of the test that was ran.
        @param delay_time_sec: Time to wait before querying the test (float).
                This is to give the VM some time to schedule the next execution.

        @returns: A boolean value indicating the success of the test.

        """
        start_time = time.time()
        while time.time() - start_time <= delay_time_sec:
            if self.tab.EvaluateJavaScript(
                    'window.__testState["%s"]' % test_name):
                return True
            time.sleep(self.POLLING_TIME)
        return False


    def test_media_source_presence(self):
        """Tests for the existence of the Media Source Extension.

        """
        self.assert_(
                self.tab.EvaluateJavaScript(
                        'window.WebKitMediaSource !== undefined'),
                msg='test_media_source_presence failed.')


    def test_attach_source(self):
        """Tests if attaching a the MediaSource to the video tag is successful.

        """
        self.tab.ExecuteJavaScript('window.__testAttach();')
        self.assert_(
                self.check_event_happened('sourceopen'),
                msg=('test_attach_source failed since "sourceopen" event did '
                     'not fire.'))


    def test_add_source_buffer(self):
        """Tests adding the source buffer to the MediaSource is successful.

        """
        self.tab.ExecuteJavaScript('window.__testAddSourceBuffer();')
        self.assert_(
                self.get_test_state('addSourceBuffer'),
                msg='test_add_source_buffer failed.')


    def test_add_supported_formats(self):
        """Tests adding supported formats to the MediaSource is successful.

        """
        self.tab.ExecuteJavaScript('window.__testAddSupportedFormats();')
        self.assert_(
                self.get_test_state('addSupportedFormats'),
                msg='test_add_supported_formats failed.')


    def test_add_source_buffer_exception(self):
        """Tests adding the source buffer to an uninitialized MediaSource.

        """
        self.tab.ExecuteJavaScript(
                'window.__testAddSourceBufferException();')
        self.assert_(
                self.get_test_state('addSourceBufferException'),
                msg='test_add_source_buffer_exception failed.')


    def test_initial_video_state(self):
        """Tests the initial states of the video object.

        """
        self.tab.ExecuteJavaScript('window.__testInitialVideoState();')
        self.assert_(
                self.get_test_state('initialVideoState'),
                msg='test_initial_video_state failed.')


    def test_initial_media_source_state(self):
        """Tests the initial states of the MediaSource object.

        """
        self.tab.ExecuteJavaScript('window.__testInitialMSState();')
        self.assert_(
                self.get_test_state('initialMSState'),
                msg='test_initial_media_source_state failed.')


    def test_can_play_clear_key(self):
        """Tests if it's possible to play ClearKey content.

        """
        self.assert_(
                self.tab.EvaluateJavaScript(
                        'window.__testCanPlayClearKey();'),
                msg='test_can_play_clear_key failed.')


    def test_can_not_play_play_ready(self):
        """Tests if it's impossible to play PlayReady.

        """
        self.assert_(
                self.tab.EvaluateJavaScript(
                        'window.__testCanNotPlayPlayReady();'),
                msg='test_can_not_play_play_ready failed.')


    def run_once(self, subtest_name):
        with chrome.Chrome() as cr:
            self.init(cr, self.PLAYER_PAGE)

            try:
                # The control file passes in a test name, which is the name of
                #  the test to run, prepended with 'test_'.
                function_to_call = getattr(self, 'test_' + subtest_name)
                function_to_call()
            except AttributeError:
                # Just in case the input test name was mistyped in the control
                #  file.
                raise error.TestFail('No function named: test_' + subtest_name)
