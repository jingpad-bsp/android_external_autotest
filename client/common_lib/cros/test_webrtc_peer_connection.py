import logging
import os
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.common_lib.cros import system_metrics_collector
from autotest_lib.client.common_lib.cros import webrtc_utils
from autotest_lib.client.cros.graphics import graphics_utils
from autotest_lib.client.cros.video import helper_logger
from telemetry.core import exceptions
from telemetry.util import image_util


EXTRA_BROWSER_ARGS = ['--use-fake-ui-for-media-stream',
                      '--use-fake-device-for-media-stream']


class WebRtcPeerConnectionTest(object):
    """
    Runs a WebRTC peer connection test.

    This class runs a test that uses WebRTC peer connections to stress Chrome
    and WebRTC. It interacts with HTML and JS files that contain the actual test
    logic. It makes many assumptions about how these files behave. See one of
    the existing tests and the documentation for run_test() for reference.
    """
    def __init__(
            self,
            title,
            own_script,
            common_script,
            bindir,
            tmpdir,
            resultsdir,
            timeout = 70,
            test_runtime_seconds = 60,
            num_peer_connections = 5,
            iteration_delay_millis = 500,
            before_start_hook = None):
        """
        Sets up a peer connection test.

        @param title: Title of the test, shown on the test HTML page.
        @param own_script: Name of the test's own JS file in bindir.
        @param tmpdir: Directory to store tmp files, should be in the autotest
                tree.
        @param bindir: The directory that contains the test files and
                own_script.
        @param resultsdir: The directory to which results, e.g. screenshots,
                should be written.
        @param timeout: Timeout in seconds for the test.
        @param test_runtime_seconds: How long to run the test. If errors occur
                the test can exit earlier.
        @param num_peer_connections: Number of peer connections to use.
        @param iteration_delay_millis: delay in millis between each test
                iteration.
        @param before_start_hook: function accepting a Chrome browser tab as
                argument. Is executed before the startTest() JS method call is
                made.
        """
        self.title = title
        self.own_script = own_script
        self.common_script = common_script
        self.bindir = bindir
        self.tmpdir = tmpdir
        self.resultsdir = resultsdir
        self.timeout = timeout
        self.test_runtime_seconds = test_runtime_seconds
        self.num_peer_connections = num_peer_connections
        self.iteration_delay_millis = iteration_delay_millis
        self.before_start_hook = before_start_hook
        self.tab = None

    def start_test(self, cr, html_file):
        """
        Opens the test page.

        @param cr: Autotest Chrome instance.
        @param html_file: File object containing the HTML code to use in the
                test. The html file needs to have the following JS methods:
                startTest(runtimeSeconds, numPeerConnections, iterationDelay)
                        Starts the test. Arguments are all numbers.
                testRunner.getStatus()
                        Gets the status of the test. Returns a string with the
                        failure message. If the string starts with 'failure', it
                        is interpreted as failure. The string 'ok-done' denotes
                        that the test is complete.
        """
        self.tab = cr.browser.tabs[0]
        self.tab.Navigate(cr.browser.platform.http_server.UrlOf(
                os.path.join(self.bindir, html_file.name)))
        self.tab.WaitForDocumentReadyStateToBeComplete()
        if self.before_start_hook is not None:
            self.before_start_hook(self.tab)
        self.tab.EvaluateJavaScript(
                "startTest(%d, %d, %d)" % (
                        self.test_runtime_seconds,
                        self.num_peer_connections,
                        self.iteration_delay_millis))

    def _test_done(self):
        """
        Determines if the test is done or not.

        Does so by querying status of the JavaScript test runner.
        @return True if the test is done, false if it is still in progress.
        @raise TestFail if the status check returns a failure status.
        """
        status = self.tab.EvaluateJavaScript('testRunner.getStatus()')
        if status.startswith('failure'):
            raise error.TestFail(
                    'Test status starts with failure, status is: ' + status)
        logging.debug(status)
        return status == 'ok-done'

    def wait_test_completed(self, timeout_secs):
        """
        Waits until the test is done.

        @param timeout_secs Max time to wait in seconds.

        @raises TestError on timeout, or javascript eval fails, or
                error status from the testRunner.getStatus() JS method.
        """
        start_secs = time.time()
        while not self._test_done():
            spent_time = time.time() - start_secs
            if spent_time > timeout_secs:
                raise utils.TimeoutError(
                        'Test timed out after {} seconds'.format(spent_time))
            self.do_in_wait_loop()

    def do_in_wait_loop(self):
        """
        Called repeatedly in a loop while the test waits for completion.

        Subclasses can override and provide specific behavior.
        """
        time.sleep(1)

    @helper_logger.video_log_wrapper
    def run_test(self):
        """
        Starts the test and waits until it is completed.
        """
        with chrome.Chrome(extra_browser_args = EXTRA_BROWSER_ARGS + \
                           [helper_logger.chrome_vmodule_flag()],
                           init_network_controller = True) as cr:
            own_script_path = os.path.join(
                    self.bindir, self.own_script)
            common_script_path = webrtc_utils.get_common_script_path(
                    self.common_script)

            # Create the URLs to the JS scripts to include in the html file.
            # Normally we would use the http_server.UrlOf method. However,
            # that requires starting the server first. The server reads
            # all file contents on startup, meaning we must completely
            # create the html file first. Hence we create the url
            # paths relative to the common prefix, which will be used as the
            # base of the server.
            base_dir = os.path.commonprefix(
                    [own_script_path, common_script_path])
            base_dir = base_dir.rstrip('/')
            own_script_url = own_script_path[len(base_dir):]
            common_script_url = common_script_path[len(base_dir):]

            html_file = webrtc_utils.create_temp_html_file(
                    self.title,
                    self.tmpdir,
                    own_script_url,
                    common_script_url)
            # Don't bother deleting the html file, the autotest tmp dir will be
            # cleaned up by the autotest framework.
            try:
                cr.browser.platform.SetHTTPServerDirectories(
                    [own_script_path, html_file.name, common_script_path])
                self.start_test(cr, html_file)
                self.wait_test_completed(self.timeout)
                self.verify_status_ok()
            finally:
                # Ensure we always have a screenshot, both when succesful and
                # when failed - useful for debugging.
                self.take_screenshots()

    def verify_status_ok(self):
        """
        Verifies that the status of the test is 'ok-done'.

        @raises TestError the status is different from 'ok-done'.
        """
        status = self.tab.EvaluateJavaScript('testRunner.getStatus()')
        if status != 'ok-done':
            raise error.TestFail('Failed: %s' % status)

    def take_screenshots(self):
        """
        Takes screenshots using two different mechanisms.

        Takes one screenshot using graphics_utils which is a really low level
        api that works between the kernel and userspace. The advantage is that
        this captures the entire screen regardless of Chrome state. Disadvantage
        is that it does not always work.

        Takes one screenshot of the current tab using Telemetry.

        Saves the screenshot in the results directory.
        """
        # Replace spaces with _ and lowercase the screenshot name for easier
        # tab completion in terminals.
        screenshot_name = self.title.replace(' ', '-').lower() + '-screenshot'
        self.take_graphics_utils_screenshot(screenshot_name)
        self.take_browser_tab_screenshot(screenshot_name)

    def take_graphics_utils_screenshot(self, screenshot_name):
        """
        Takes a screenshot of what is currently displayed.

        Uses the low level graphics_utils API.

        @param screenshot_name: Name of the screenshot.
        """
        try:
            full_filename = screenshot_name + '_graphics_utils'
            graphics_utils.take_screenshot(self.resultsdir, full_filename)
        except StandardError as e:
            logging.warn('Screenshot using graphics_utils failed', exc_info = e)

    def take_browser_tab_screenshot(self, screenshot_name):
        """
        Takes a screenshot of the current browser tab.

        @param screenshot_name: Name of the screenshot.
        """
        if self.tab is not None and self.tab.screenshot_supported:
            try:
                screenshot = self.tab.Screenshot(timeout = 10)
                full_filename = os.path.join(
                        self.resultsdir, screenshot_name + '_browser_tab.png')
                image_util.WritePngFile(screenshot, full_filename)
            except exceptions.Error as e:
                # This can for example occur if Chrome crashes. It will
                # cause the Screenshot call to timeout.
                logging.warn(
                        'Screenshot using telemetry tab.Screenshot failed',
                        exc_info = e)
        else:
            logging.warn(
                    'Screenshot using telemetry tab.Screenshot() not supported')



class WebRtcPeerConnectionPerformanceTest(WebRtcPeerConnectionTest):
    """
    Runs a WebRTC performance test.
    """
    def __init__(
            self,
            title,
            own_script,
            common_script,
            bindir,
            tmpdir,
            resultsdir,
            timeout = 70,
            test_runtime_seconds = 60,
            num_peer_connections = 5,
            iteration_delay_millis = 500,
            before_start_hook = None):
          super(WebRtcPeerConnectionPerformanceTest, self).__init__(
                  title,
                  own_script,
                  common_script,
                  bindir,
                  tmpdir,
                  resultsdir,
                  timeout,
                  test_runtime_seconds,
                  num_peer_connections,
                  iteration_delay_millis,
                  before_start_hook)
          self.collector = system_metrics_collector.SystemMetricsCollector()

    def do_in_wait_loop(self):
        self.collector.collect_snapshot()
        time.sleep(1)

