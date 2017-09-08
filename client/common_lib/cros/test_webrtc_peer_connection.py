import logging
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.common_lib.cros import webrtc_utils
from autotest_lib.client.cros.video import helper_logger


EXTRA_BROWSER_ARGS = ['--use-fake-ui-for-media-stream',
                      '--use-fake-device-for-media-stream']


class WebRtcPeerConnectionTest:
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
        self.timeout = timeout
        self.test_runtime_seconds = test_runtime_seconds
        self.num_peer_connections = num_peer_connections
        self.iteration_delay_millis = iteration_delay_millis
        self.before_start_hook = before_start_hook
        self.tab = None

    def start_test(self, cr, html_file):
        """Opens the test page.

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

    def wait_test_completed(self, timeout_secs):
        """
        Waits until the test is done.

        @param timeout_secs Max time to wait in seconds.

        @raises TestError on timeout, or javascript eval fails, or
                error status from the testRunner.getStatus() JS method.
        """
        def _test_done():
            status = self.tab.EvaluateJavaScript('testRunner.getStatus()')
            if status.startswith('failure'):
                raise error.TestFail(
                        'Test status starts with failure, status is: ' + status)
            logging.debug(status)
            return status == 'ok-done'

        utils.poll_for_condition(
                _test_done, timeout=timeout_secs, sleep_interval=1,
                desc='test reports itself as finished')

    @helper_logger.video_log_wrapper
    def run_test(self):
        """Starts the test and waits until it is completed."""
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
            cr.browser.platform.SetHTTPServerDirectories(
                [own_script_path, html_file.name, common_script_path])
            self.start_test(cr, html_file)
            self.wait_test_completed(self.timeout)
            self.verify_status_ok()

    def verify_status_ok(self):
        """Verifies that the status of the test is 'ok-done'.

        @raises TestError the status is different from 'ok-done'.
        """
        status = self.tab.EvaluateJavaScript('testRunner.getStatus()')
        if status != 'ok-done':
            raise error.TestFail('Failed: %s' % status)

