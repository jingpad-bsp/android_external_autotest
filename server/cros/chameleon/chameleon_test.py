# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time
import xmlrpclib

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import chameleon_port_finder
from autotest_lib.client.cros.chameleon import edid
from autotest_lib.client.cros.chameleon import screen_test
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class ChameleonTest(test.test):
    """This is the base class of Chameleon tests.

    This base class initializes Chameleon board and its related services,
    like connecting Chameleond and DisplayFacade. Also kills the connections
    on cleanup.
    """

    _TIMEOUT_VIDEO_STABLE_PROBE = 10

    def initialize(self, host):
        """Initializes.

        @param host: The Host object of DUT.
        """
        factory = remote_facade_factory.RemoteFacadeFactory(host)
        self.audio_facade = factory.create_audio_facade()
        self.display_facade = factory.create_display_facade()
        self.chameleon = host.chameleon
        self.host = host
        # TODO(waihong): Support multiple connectors.
        self.chameleon_port = self._get_connected_port()
        self.screen_test = screen_test.ScreenTest(
                self.chameleon_port, self.display_facade, self.outputdir)
        self._platform_prefix = host.get_platform().lower().split('_')[0]


    def is_edid_supported(self, tag, width, height):
        """Check whether the EDID is supported by DUT

        @param tag: The tag of the EDID file; 'HDMI' or 'DP'
        @param width: The screen width
        @param height: The screen height

        @return: True if the check passes; False otherwise.
        """
        # TODO: This is a quick workaround; some of our arm devices so far only
        # support the HDMI EDIDs and the DP one at 1680x1050. A more proper
        # solution is to build a database of supported resolutions and pixel
        # clocks for each model and check if the EDID is in the supported list.
        if self._platform_prefix in ('snow', 'spring', 'skate', 'peach'):
            if tag == 'DP':
                return width == 1680 and height == 1050
        return True


    def backup_edid(self):
        """Backups the original EDID."""
        logging.info('Backups the original EDID...')
        self._original_edid = self.chameleon_port.read_edid()
        self._original_edid_path = os.path.join(self.outputdir, 'original_edid')
        self._original_edid.to_file(self._original_edid_path)


    def restore_edid(self):
        """Restores the original EDID, if any."""
        if (hasattr(self, 'chameleon_port') and self.chameleon_port and
                hasattr(self, '_original_edid') and self._original_edid):
            current_edid = self.chameleon_port.read_edid()
            if self._original_edid.data != current_edid.data:
                logging.info('Restore the original EDID...')
                self.chameleon_port.apply_edid(self._original_edid)
                # Remove the original EDID file after restore.
                os.remove(self._original_edid_path)
                self._original_edid = None


    def apply_edid_file(self, filename):
        """Load the EDID file onto Chameleon with logging.

        @param filename: the path of edid file.
        """

        if not hasattr(self, '_original_edid') or not self._original_edid:
            self.backup_edid()
        logging.info('Apple EDID on port %d (%s): %s',
                     self.chameleon_port.get_connector_id(),
                     self.chameleon_port.get_connector_type(),
                     filename)
        self.chameleon_port.apply_edid(edid.Edid.from_file(filename))


    def is_display_primary(self, internal=True):
        """Checks if internal screen is primary display.

        @param internal: is internal/external screen primary status requested

        @return boolean True if internal display is primary."""

        display_info = self.display_facade.get_display_info()

        for display_index in xrange(len(display_info)):
            current_display = display_info[display_index]
            if current_display.is_internal is internal and current_display.is_primary:
                return True
        return False


    def is_mirrored_enabled(self):
        """Checks the mirrored state.

        @return True if mirrored mode is enabled.
        """
        return self.display_facade.is_mirrored_enabled()


    def set_mirrored(self, test_mirrored):
        """Sets the external display is in mirrored mode or extended mode

        @param test_mirrored: True if in mirrored mode, otherwise in
                extended mode.
        """

        logging.info('Set mirrored: %s', test_mirrored)
        self.display_facade.set_mirrored(test_mirrored)


    def suspend_resume(self, suspend_time=10, timeout=20):
        """Suspends and resumes the DUT.

        @param suspend_time: suspend time in second, default: 10s.
        @param timeout: time to wait for DUP to fully resume (second).
        """

        start_time = time.time()
        boot_id = self.host.get_boot_id()
        logging.info('Suspend and resume %.2f seconds', suspend_time)
        try:
            self.display_facade.suspend_resume(suspend_time)
        except xmlrpclib.Fault as e:
            # Log suspend/resume errors but continue the test.
            logging.error('suspend_resume error: %s', str(e))
        # The following call raises a TestFail if boot_id's don't match or
        # timed out.
        self.host.test_wait_for_resume(boot_id, timeout)
        logging.info('DUT is up within %.2f seconds', time.time() - start_time)


    def reboot(self, wait=True):
        """Reboots the DUT with logging.

        @param wait: True if want to wait DUT up and reconnect to
                display facade"""

        logging.info('Reboot...')
        self.host.reboot(wait=wait)
        if wait:
           self.display_facade.connect()


    def wait_for_output(self, output):
        """Waits for the specified output to be connected.

        @param output: name of the output in a string.
        @raise error.TestFail if output fails to get connected.
        """
        if not self.display_facade.wait_for_output(output):
            raise error.TestFail('Fail to get %s connected' % output)


    def reconnect_output(self, unplug_duration_sec=5):
        """Reconnects the output with an unplug followed by a plug.

        @param unplug_duration_sec: duration of unplug in second.
        """
        logging.info('Reconnect output...')
        output = self.get_dut_display_connector()
        self.chameleon_port.unplug()
        time.sleep(unplug_duration_sec)
        self.chameleon_port.plug()
        self.wait_for_output(output)


    def cleanup(self):
        """Cleans up."""
        if hasattr(self, 'chameleon') and self.chameleon:
          retry_count = 2
          while not self.chameleon.is_healthy() and retry_count >= 0:
              logging.info('Chameleon is not healthy. Try to repair it... '
                           '(%d retrys left)', retry_count)
              self.chameleon.repair()
              retry_count = retry_count - 1
          if self.chameleon.is_healthy():
              logging.info('Chameleon is healthy.')
          else:
              logging.warning('Chameleon is not recovered after repair.')

        # Unplug the Chameleon port, not to affect other test cases.
        if hasattr(self, 'chameleon_port') and self.chameleon_port:
            self.chameleon_port.unplug()
        self.restore_edid()


    def _get_connected_port(self):
        """Gets the first connected output port between Chameleon and DUT.

        This method also plugs this port at the end.

        @return: A ChameleonPort object.
        """
        self.chameleon.reset()
        finder = chameleon_port_finder.ChameleonVideoInputFinder(
                self.chameleon, self.display_facade)
        ports = finder.find_all_ports()
        if len(ports.connected) == 0:
            raise error.TestError('DUT and Chameleon board not connected')
        # Plug the first port and return it.
        first_port = ports.connected[0]
        first_port.plug()
        first_port.wait_video_input_stable(self._TIMEOUT_VIDEO_STABLE_PROBE)
        return first_port


    def get_dut_display_connector(self):
        """Gets the name of the connected display connector of DUT.

        @return: A string for the connector name."""
        connector = self.display_facade.get_external_connector_name()
        logging.info('See the display on DUT: %s', connector)
        return connector


    def check_external_display_connector(self, expected_connector, timeout=5):
        """Checks the connecting status of external display on DUT.

        @param expected_connector: Name of the expected connector or False
                if no external monitor is expected.
        @param timeout: Duration in second to retry checking the connector.
        @raise error.TestFail if the check does not pass.
        """
        current_connector = self.get_dut_display_connector()
        now = time.time()
        end_time = now + timeout
        while expected_connector != current_connector and now < end_time:
            logging.info('Expect to see %s but got %s', expected_connector,
                    current_connector)
            time.sleep(0.5)
            now = time.time()
            current_connector = (
                    self.display_facade.get_external_connector_name())

        if expected_connector != current_connector:
            if expected_connector:
                error_message = 'Expect to see %s but got %s' % (
                        expected_connector, current_connector)
            else:
                error_message = ('Do not expect to see external monitor '
                        'but got %s' % (current_connector))
            raise error.TestFail(error_message)
        logging.info('External display connector: %s', current_connector)


    def raise_on_errors(self, check_results):
        """If there is any error message in check_results, raise it.

        @param check_results: A list of check results."""

        check_results = [x for x in check_results if x is not None]
        if check_results:
            raise error.TestFail('; '.join(set(check_results)))


    def audio_start_recording(self, host, port):
        """Starts recording audio on a host using a port.

        @param host: The host to start recording. E.g. 'Chameleon' or 'DUT'.
                     Currently only 'Chameleon' is supported.
        @param port: The port to record audio. Currently only 'HDMI' is
                     supported.

        @returns: It depends on start_capturing_audio implementation on
                  different host and port.

        @raises: NotImplementedError if host/port is not supported.
        """
        if host == 'Chameleon':
            if port != self.chameleon_port.get_connector_type():
                raise ValueError(
                        'Port %s is not connected to Chameleon.' % port)
            if port == 'HDMI':
                return self.chameleon_port.start_capturing_audio()
            raise NotImplementedError(
                    'Audio recording from %s is not supported' % port)
        raise NotImplementedError('Audio recording on %s using %s is not '
                                  'supported' % (host, port))

    def audio_stop_recording(self, host, port):
        """Stops recording audio on a host using a port.

        @param host: The host to stop recording. E.g. 'Chameleon' or 'DUT'.
                     Currently only 'Chameleon' is supported.
        @param port: The port to record audio. Currently only 'HDMI' is
                     supported.

        @returns: It depends on stop_capturing_audio implementation on
                  different host and port.

        @raises: NotImplementedError if host/port is not supported.
        """
        if host == 'Chameleon':
            if port != self.chameleon_port.get_connector_type():
                raise ValueError(
                        'Port %s is not connected to Chameleon.' % port)
            # TODO(cychiang): Handle multiple chameleon ports.
            if port == 'HDMI':
                return self.chameleon_port.stop_capturing_audio()
            raise NotImplementedError(
                    'Audio recording from %s is not supported' % port)
        raise NotImplementedError('Audio recording on %s using %s is not '
                                  'supported' % (host, port))

    def audio_playback(self, host, file_name):
        """Starts playback audio on a host.

        @param host: The host to playback audio. E.g. 'Chameleon' or 'DUT'.
                     Currently only 'DUT' is supported.
        @param file_name: The path to the file on the host.

        @returns: It depends on playback implementation on
                  different host.

        """
        if host == 'DUT':
            return self.audio_facade.playback(file_name)
        raise NotImplementedError(
                'Audio recording on %s is not supported' % host)
