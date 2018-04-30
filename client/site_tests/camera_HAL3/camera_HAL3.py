# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A test which verifies the camera function with HAL3 interface."""

import logging
import os
import xml.etree.ElementTree
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import service_stopper
from sets import Set

class camera_HAL3(test.test):
    """
    This test is a wrapper of the test binary cros_camera_test.
    """

    version = 1
    test_binary = 'cros_camera_test'
    dep = 'camera_hal3'
    cros_camera_service = 'cros-camera'
    media_profiles_path = os.path.join('vendor', 'etc', 'media_profiles.xml')
    tablet_board_list = ['scarlet']
    enable_test_mode_path = '/run/camera/enable_test'

    def setup(self):
        """
        Run common setup steps.
        """
        self.dep_dir = os.path.join(self.autodir, 'deps', self.dep)
        self.job.setup_dep([self.dep])
        logging.debug('mydep is at %s', self.dep_dir)

    def cleanup(self):
        """Autotest cleanup function

        It is run by common_lib/test.py.
        """
        os.remove(self.enable_test_mode_path)

    def run_function_test(self, cmd, timeout):
        """
        Verify camera function with HAL3 interface.

        @param cmd: Test command.
        @param timeout: Seconds. Timeout for running the test command.
        """
        xml_content = utils.system_output(
            ' '.join(['android-sh', '-c', '\"cat',
                      self.media_profiles_path + '\"']))
        root = xml.etree.ElementTree.fromstring(xml_content)
        recording_params = Set()
        for camcorder_profiles in root.findall('CamcorderProfiles'):
            for encoder_profile in camcorder_profiles.findall('EncoderProfile'):
                video = encoder_profile.find('Video')
                recording_params.add('%s:%s:%s:%s' % (
                    camcorder_profiles.get('cameraId'), video.get('width'),
                    video.get('height'), video.get('frameRate')))
        if recording_params:
            cmd.append('--recording_params=' + ','.join(recording_params))
        if utils.get_current_board() in self.tablet_board_list:
            cmd.append('--gtest_filter=-*SensorOrientationTest/*')

        utils.system(' '.join(cmd), timeout=timeout)

    def run_test_with_options(self, cmd, timeout, options):
        """
        Verify things by the output of the test command.

        @param cmd: Test command.
        @param timeout: Seconds. Timeout for running the test command.
        @param options: Option strings passed to test command. e.g. ['--v=1']
        """
        for option in options:
            # if we specify camera hal in option, we need to check if
            # there is a camera hal in DUT.
            if 'camera_hal_path' in option:
                hal = option.split('=')[1]
                if not os.path.exists(hal):
                    raise error.TestNAError('There is no hal %s' % hal)
            cmd.append(option)
        utils.system(' '.join(cmd), timeout=timeout)

    def run_once(self, timeout=600, options=[]):
        """
        Entry point of this test.

        @param timeout: Seconds. Timeout for running the test command.
        @param options: Option strings passed to test command. e.g. ['--v=1']
        """
        self.job.install_pkg(self.dep, 'dep', self.dep_dir)

        # create file to enable camera test mode.
        # Why don't we put it in setup()? The setup() is called in compile
        # time and it causes compile error.
        open(self.enable_test_mode_path, 'a').close()

        with service_stopper.ServiceStopper([self.cros_camera_service]):
            cmd = [ os.path.join(self.dep_dir, 'bin', self.test_binary) ]
            if options:
                self.run_test_with_options(cmd, timeout, options)
            else:
                self.run_function_test(cmd, timeout)
