# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

from PIL import Image
from PIL import ImageChops

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import edid
from autotest_lib.server import test
from autotest_lib.server.cros.chameleon import multimedia_client_factory

def _unlevel(p):
    """Unlevel a color value from TV level back to PC level

    @param p: The color value in one character byte

    @return: The color value in integer in PC level
    """
    # TV level: 16~236; PC level: 0~255
    p = (p - 126) * 128 / 110 + 128
    if p < 0:
        p = 0
    elif p > 255:
        p = 255
    return p


class ChameleonTest(test.test):
    """This is the base class of Chameleon tests.

    This base class initializes Chameleon board and its related services,
    like connecting Chameleond and DisplayClient. Also kills the connections
    on cleanup.
    """

    _TIMEOUT_VIDEO_STABLE_PROBE = 10

    _PIXEL_DIFF_VALUE_MARGIN_FOR_ANALOG_SIGNAL = 5
    _PIXEL_DIFF_VALUE_MARGIN_FOR_DIGITAL_SIGNAL = 1

    def initialize(self, host):
        """Initializes.

        @param host: The Host object of DUT.
        """
        factory = multimedia_client_factory.MultimediaClientFactory(host)
        self.audio_client = factory.create_audio_client()
        self.display_client = factory.create_display_client()
        self.chameleon = host.chameleon
        self.host = host
        self.chameleon_port = self._get_connected_port()
        if self.chameleon_port is None:
            raise error.TestError('DUT and Chameleon board not connected')
        self._platform_prefix = host.get_platform().lower().split('_')[0]
        self._unlevel_func = None
        if self._platform_prefix in ('snow', 'spring', 'skate', 'peach'):
            self._unlevel_func =  _unlevel


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


    def load_test_image(self, image_size, calibration_image_setup_time=10):
        """Load calibration image on the DUT with logging

        @param image_size: A tuple (width, height) conforms the resolution.
        @param calibration_image_setup_time: Time to wait for the full screen
                bubble and the external display detecting notation to disappear.
        """

        self.display_client.load_calibration_image(image_size)
        self.display_client.hide_cursor()
        logging.info('Waiting for calibration image to stabilize.')
        time.sleep(calibration_image_setup_time)


    def unload_test_image(self):
        """Close the tab in browser to unload test image"""

        self.display_client.close_tab()


    def set_resolution(self, display_index, width, height):
        """Sets the resolution on the specified display.

        @param display_index: index of the display to set resolutions for; 0 is
                the internal one for chromebooks.
        @param width: width of the resolution
        @param height: height of the resolution
        """

        logging.info('Display %d: Set resolution to %d x %d', display_index,
            width, height)
        self.display_client.set_resolution(display_index, width, height)


    def get_first_external_display_resolutions(self):
        """Gets the first external display and its resolutions.

        @return a tuple (display_index, available resolutions).
        @raise error.TestFail if no external display is found. """
        # TODO (tingyuan): Gets complete display modes data, instead of
        # resolution, to facilitate the subsequent use. (i.e. for image size)
        display_info = self.display_client.get_display_info()
        test_display_index = None

        # get first external and enabled display
        for display_index in xrange(len(display_info)):
            current_display = display_info[display_index]
            if current_display.is_internal or (
                    not current_display.is_enabled):
                logging.info('Display %d (%s): %s%sdisplay, '
                        'skipped.' , display_index,
                        current_display.display_id,
                        "Internal " if current_display.is_internal else "",
                        "Disabled " if not current_display.is_enabled else
                        "")
                continue

            test_display_index = display_index
            break

        if test_display_index is None:
            raise error.TestFail("No external display is found.")

        resolutions = self.display_client.get_available_resolutions(
                test_display_index)

        logging.info('External display %d (%s)%s: %d resolutions found.',
                test_display_index, current_display.display_id,
                " (Primary)" if current_display.is_primary else "",
                len(resolutions))

        return display_index, resolutions


    def set_mirrored(self, test_mirrored):
        """Sets the external display is in mirrored mode or extended mode

        @param test_mirrored: True if in mirrored mode, otherwise in
                extended mode.
        """

        logging.info('Set mirrored: %s', test_mirrored)
        self.display_client.set_mirrored(test_mirrored)


    def suspend_resume(self, suspend_time=10, timeout=20):
        """Suspends and resumes the DUT.
        @param suspend_time: suspend time in second, default: 10s.
        @param timeout: time to wait for DUP to fully resume (second)"""

        start_time = time.time()
        logging.info('Suspend and resume %.2f seconds', suspend_time)
        self.display_client.suspend_resume(suspend_time)
        if self.host.wait_up(timeout):
            logging.info('DUT is up within %.2f '
                    'second(s).', time.time() - start_time)
        else:
            raise error.TestError('DUT is not up after resume')


    def reboot(self, wait=True):
        """Reboots the DUT with logging.

        @param wait: True if want to wait DUT up and reconnect to
                display client"""

        logging.info('Reboot...')
        self.host.reboot(wait=wait)
        if wait:
           self.display_client.connect()


    def reconnect_output(self, unplug_duration_sec=0.5):
        """Reconnects the output with an unplug followed by a plug.

        @param unplug_duration_sec: duration of unplug in second.
        """
        logging.info('Reconnect output...')
        output = self.display_client.get_external_connector_name()
        self.chameleon_port.unplug()
        time.sleep(unplug_duration_sec)
        self.chameleon_port.plug()
        self.display_client.wait_for_output(output)


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

        @return: A ChameleonPort object.
        """
        self.chameleon.reset()
        # TODO(waihong): Support multiple connectors.
        for chameleon_port in self.chameleon.get_all_ports():
            connector_type = chameleon_port.get_connector_type()
            # Plug to ensure the connector is plugged.
            chameleon_port.plug()
            # Don't care about video input stable in the end or timeout.
            # It will be checked on the matching of the connect names.
            chameleon_port.wait_video_input_stable(
                    self._TIMEOUT_VIDEO_STABLE_PROBE)
            output = self.display_client.get_external_connector_name()

            # TODO(waihong): Make sure eDP work in this way.
            if output and output.startswith(connector_type):
                return chameleon_port
            # Unplug the port if it is not the connected.
            chameleon_port.unplug()
        return None


    def get_dut_display_connector(self):
        """Gets the name of the connected display connector of DUT.

        @return: A string for the connector name."""
        connector = self.display_client.get_external_connector_name()
        logging.info('See the display on DUT: %s', connector)
        return connector


    def check_external_display_connector(self, expected_connector, timeout=5):
        """Checks the connecting status of external display on DUT.

        @param expected_connector: Name of the expected connector or None
                if no external monitor is expected.
        @param timeout: Duration in second to retry checking the connector.
        @raise error.TestFail if the check does not pass.
        """
        current_connector = self.display_client.get_external_connector_name()
        if not current_connector:
            current_connector = None
        now = time.time()
        end_time = now + timeout
        while expected_connector != current_connector and now < end_time:
            logging.info('Expected to see %s but got %s',
                    (expected_connector, current_connector))
            time.sleep(0.5)
            now = time.time()
            current_connector = self.display_client.get_external_connector_name()

        if expected_connector != current_connector:
            if expected_connector:
                error_message = 'Expected to see %s but got %s' % (
                        expected_connector, current_connector)
            else:
                error_message = ('Do not expect to see external monitor '
                        'but got %s' % (current_connector))
            raise error.TestFail(error_message)
        logging.info('External display connector: %s', current_connector)


    def check_screen_resolution(self, expected_resolution, tag='',
                                under_mirrored_mode=True):
        """Checks the resolution for DUT external screen with Chameleon.
        1. Verify that the resolutions of both DUT and Chameleon match the
                expected one.
        2. Verify that the resolution of DUT match that of Chameleon. If not,
                break the test.
        @param tag: A string of tag for the prefix of output filenames.
        @param expected_resolution: A tuple (width, height) for the expected
                resolution.
        @param under_mirrored_mode: True if don't make fails error on check the
                resolution between dut and expected.
        @return: None if the check passes; otherwise, a string of error message.
        """
        # Verify the actual resolution detected by chameleon and dut
        # are the same as what is expected.

        chameleon_resolution = self.chameleon_port.get_resolution()
        dut_resolution = self.display_client.get_resolution()

        logging.info('Checking resolution with Chameleon (tag: %s).', tag)
        if expected_resolution != dut_resolution or (
                chameleon_resolution != dut_resolution):
            message = (
                        'Detected a different resolution: '
                        'dut: %r; chameleon: %r; expected %r' %
                        (dut_resolution,
                         chameleon_resolution,
                         expected_resolution))
            # Note: In mirrored mode, the device may be in hardware mirror
            # (as opposed to software mirror). If so, the actual resolution
            # could be different from the expected one. So we skip the check
            # in mirrored mode. The resolution of the DUT and Chameleon
            # should be same no matter the device in mirror mode or not.
            if chameleon_resolution != dut_resolution or (
                    not under_mirrored_mode):
                logging.error(message)
                return message
            else:
                logging.warn(message)
        return None


    def raise_on_errors(self, check_results):
        """If there is any error message in check_results, raise it.

        @param check_results: A list of check results."""

        check_results = [x for x in check_results if x is not None]
        if check_results:
            raise error.TestFail('; '.join(set(check_results)))


    def set_plug(self, plug_status):
        """Sets plug/unplug by plug_status.

        @param plug_status: True for plug"""
        logging.info('Set plug: %s', plug_status)
        if plug_status:
            self.chameleon_port.plug()
        else:
            self.chameleon_port.unplug()


    def _compare_images(self, tag, image_a, image_b, pixel_diff_value_margin=0,
            total_wrong_pixels_margin=0):
        """Compares 2 screen image.

        @param tag: A string of tag.
        @param image_a: The first image object for comparing.
        @param image_b: The second image object for comparing.
        @param pixel_diff_value_margin: The margin for comparing a pixel. Only
                if a pixel difference exceeds this margin, will treat as a wrong
                pixel. Sets None means using default value by detecting
                connector type.
        @param total_wrong_pixels_margin: The margin for the number of wrong
                pixels. If the total number of wrong pixels exceeds this margin,
                the check fails.
        @return: None if the check passes; otherwise, a string of error message.
        """

        # The size property is the resolution of the image.
        logging.info('Comparing the images of %s...', tag)
        if image_a.size != image_b.size:
            message = ('Result of %s: size not match: %r != %r' %
                       (tag, image_a.size, image_b.size))
            logging.error(message)
            return message

        diff_image = ImageChops.difference(image_a, image_b)
        histogram = diff_image.convert('L').histogram()

        total_wrong_pixels = sum(histogram[pixel_diff_value_margin + 1:])
        max_diff_value = max(filter(
                lambda x: histogram[x], xrange(len(histogram))))
        if total_wrong_pixels > 0:
            logging.debug('Histogram of difference: %r', histogram)
            message = ('Result of %s: total %d wrong pixels (diff up to %d)'
                       % (tag, total_wrong_pixels, max_diff_value))
            if total_wrong_pixels > total_wrong_pixels_margin:
                logging.error(message)
                return message

            message += (', within the acceptable range %d' %
                        total_wrong_pixels_margin)
            logging.warning(message)
        else:
            logging.info('Result of %s: all pixels match (within +/- %d)',
                         tag, max_diff_value)
        return None


    def check_screen_with_chameleon(
            self, tag, pixel_diff_value_margin=None,
            total_wrong_pixels_margin=0, verify_mirrored=True):
        """Checks the DUT external screen with Chameleon.

        1. Capture the whole screen from the display buffer of Chameleon.
        2. Capture the framebuffer on DUT.
        3. Verify that the captured screen match the content of DUT framebuffer.

        @param tag: A string of tag.
        @param pixel_diff_value_margin: The margin for comparing a pixel. Only
                if a pixel difference exceeds this margin, will treat as a wrong
                pixel. Sets None means using default value by detecting
                connector type.
        @param total_wrong_pixels_margin: The margin for the number of wrong
                pixels. If the total number of wrong pixels exceeds this margin,
                the check fails.
        @param verify_mirrored: True if compare the internal screen and
                the external screen when the resolution matches.
        @return: None if the check passes; otherwise, a string of error message.
        """

        if pixel_diff_value_margin is None:
            # Tolerate pixel errors differently for VGA.
            if self.display_client.get_external_connector_name() == 'VGA':
                pixel_diff_value_margin = (
                        self._PIXEL_DIFF_VALUE_MARGIN_FOR_ANALOG_SIGNAL)
            else:
                pixel_diff_value_margin = (
                        self._PIXEL_DIFF_VALUE_MARGIN_FOR_DIGITAL_SIGNAL)

        logging.info('Capturing framebuffer on Chameleon...')
        chameleon_image = self.chameleon_port.capture_screen()
        if self._unlevel_func:
            chameleon_image = Image.eval(chameleon_image, self._unlevel_func)

        logging.info('Capturing framebuffer on external display of DUT...')
        dut_image_external = self.display_client.capture_external_screen()

        if dut_image_external is None:
            message = 'Failed to capture the external screen image.'
            logging.error(message)
            return message

        if verify_mirrored:
            internal_resolution = (
                    self.display_client.get_internal_display_resolution())
            if 0 in internal_resolution:
                logging.info('Failed to get the resolution of internal'
                             ' display: %r, skip the mirroring verify test.',
                             internal_resolution)
                verify_mirrored = False
            elif dut_image_external.size != internal_resolution:
                logging.info('Size of external and internal screen not match'
                             ': %r != %r', dut_image_external.size,
                             internal_resolution)
                logging.info('In software based mirrored mode, '
                             'skip the mirroring verify test.')
                verify_mirrored = False

        if verify_mirrored:
            logging.info('Capturing framebuffer on internal display of DUT...')
            dut_image_internal = self.display_client.capture_internal_screen()
            if dut_image_internal is None or (
                    dut_image_internal.size != internal_resolution):
                message = 'Failed to capture the internal screen image.'
                logging.error(message)
                return message

        message = None
        try:
            message = self._compare_images(
                    "%s_C_E" % tag, chameleon_image, dut_image_external,
                    pixel_diff_value_margin, total_wrong_pixels_margin)
            if message:
                return message
            if verify_mirrored:
                message = self._compare_images(
                        "%s_C_I" % tag, chameleon_image, dut_image_internal,
                        pixel_diff_value_margin, total_wrong_pixels_margin)
                if message:
                    return message
        finally:
            if message is None:
                return None
            chameleon_image.save(
                    os.path.join(self.outputdir, '%s-chameleon.png' % tag))
            dut_image_external.save(os.path.join(
                    self.outputdir, '%s-dut-external.png' % tag))
            if verify_mirrored:
                dut_image_internal.save(os.path.join(
                        self.outputdir, '%s-dut-internal.png' % tag))


    def load_test_image_and_check(self, tag, expected_resolution,
            pixel_diff_value_margin=None, total_wrong_pixels_margin=0,
            under_mirrored_mode=True, error_list = None):
        """Loads the test image and checks the image on Chameleon.

        1. Checks resolution.
        2. Checks screen between Chameleon and DUT.

        @param tag: A string of tag for the prefix of output filenames.
        @param expected_resolution: A tuple (width, height) for the expected
                resolution.
        @param pixel_diff_value_margin: The margin for comparing a pixel. Only
                if a pixel difference exceeds this margin, will treat as a wrong
                pixel. Sets None means using default value by detecting
                connector type.
        @param total_wrong_pixels_margin: The margin for the number of wrong
                pixels. If the total number of wrong pixels exceeds this margin,
                the check fails.
        @param under_mirrored_mode: True if don't make fails error on check the
                resolution between dut and expected. It will also compare the
                internal screen and the external screen.
        @param error_list: A list to append the error message to or None.
        @return: None if the check passes; otherwise, a string of error message.
        """
        # TODO(tingyuan): Check test_image is keeping full-screen.

        error_message = self.check_screen_resolution(
                expected_resolution, tag, under_mirrored_mode)
        if error_message:
            if error_list is not None:
                error_list.append(error_message)
            return error_message

        dut_resolution = self.display_client.get_resolution()

        try:
            self.load_test_image(dut_resolution)
            error_message = self.check_screen_with_chameleon(
                    tag, pixel_diff_value_margin, total_wrong_pixels_margin,
                    under_mirrored_mode)
            if error_message:
                if error_list is not None:
                    error_list.append(error_message)
                return error_message
        finally:
            self.unload_test_image()

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
            return self.audio_client.playback(file_name)
        raise NotImplementedError(
                'Audio recording on %s is not supported' % host)
