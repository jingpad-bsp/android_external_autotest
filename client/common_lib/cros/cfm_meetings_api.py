# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

DEFAULT_TIMEOUT = 30
TELEMETRY_API = 'hrTelemetryApi'


class CfmMeetingsAPI(object):
    """Utility class for interacting with CfMs."""

    def __init__(self, webview_context):
        self._webview_context = webview_context

    def _execute_telemetry_command(self, command):
        self._webview_context.ExecuteJavaScript(
            'window.%s.%s' % (TELEMETRY_API, command))

    def _evaluate_telemetry_command(self, command):
        return self._webview_context.EvaluateJavaScript(
            'window.%s.%s' % (TELEMETRY_API, command))

    # UI commands/functions
    def wait_for_oobe_start_page(self):
        """Wait for oobe start screen to launch."""
        self._webview_context.WaitForJavaScriptCondition(
                'window.hasOwnProperty("hrOobIsStartPageForTest") '
                '&& window.hrOobIsStartPageForTest() === true',
                timeout=DEFAULT_TIMEOUT)
        logging.info('Reached oobe start page')

    def wait_for_meetings_landing_page(self):
        """Waits for the landing page screen."""
        self._webview_context.WaitForJavaScriptCondition(
            'window.hasOwnProperty("%s")' % TELEMETRY_API,
            timeout=DEFAULT_TIMEOUT)
        utils.poll_for_condition(
            lambda: not self._evaluate_telemetry_command('isInMeeting()'),
            exception=error.TestFail('Timed out waiting for landing page.'),
            timeout=DEFAULT_TIMEOUT,
            sleep_interval=1)
        logging.info('Reached meetings landing page.')

    def wait_for_meetings_in_call_page(self):
        """Waits for the in-call page to launch."""
        self._webview_context.WaitForJavaScriptCondition(
            'window.hasOwnProperty("%s")' % TELEMETRY_API,
            timeout=DEFAULT_TIMEOUT)
        utils.poll_for_condition(
            lambda: self.is_in_meeting_session(),
            exception=error.TestFail('Not able to start meeting session.'),
            timeout=DEFAULT_TIMEOUT,
            sleep_interval=1)
        logging.info('Reached meetings in-call page.')

    def skip_oobe_screen(self):
        """Skip Chromebox for Meetings oobe screen."""
        self._webview_context.ExecuteJavaScript('window.hrOobSkipForTest()')
        self.wait_for_meetings_landing_page()
        logging.info('Skipped oobe screen.')

    def is_oobe_start_page(self):
        """Check if device is on CFM oobe start screen."""
        if self._webview_context.EvaluateJavaScript(
                'window.hrOobIsStartPageForTest()'):
            logging.info('Is on oobe start page.')
            return True
        logging.info('Is not on oobe start page.')
        return False

    # Hangouts commands/functions
    def join_meeting_session(self, meeting_name):
        """Joins a meeting.

        @param meeting_name: Name of the meeting session.
        """
        if self.is_in_meeting_session():
            self.end_meeting_session()

        self._execute_telemetry_command('joinMeeting("%s")' % meeting_name)
        self.wait_for_meetings_in_call_page()
        logging.info('Started meeting session: %s', meeting_name)

    def end_meeting_session(self):
        """End current meeting session."""
        self._execute_telemetry_command('endCall()')
        self.wait_for_meetings_landing_page()
        logging.info('Ended meeting session.')

    def is_in_meeting_session(self):
        """Check if device is in meeting session."""
        if self._evaluate_telemetry_command('isInMeeting()'):
            logging.info('Is in meeting session.')
            return True
        logging.info('Is not in meeting session.')
        return False

    # Mic audio commands/functions
    def is_mic_muted(self):
        """Check if mic is muted."""
        if self._evaluate_telemetry_command('isMicMuted()'):
            logging.info('Mic is muted.')
            return True
        logging.info('Mic is not muted.')
        return False

    def mute_mic(self):
        """Local mic mute from toolbar."""
        self._execute_telemetry_command('setMicMuted(true)')
        logging.info('Locally muted mic.')

    def unmute_mic(self):
        """Local mic unmute from toolbar."""
        self._execute_telemetry_command('setMicMuted(false)')
        logging.info('Locally unmuted mic.')

    def get_mic_devices(self):
        """Get all mic devices detected by hotrod."""
        return self._evaluate_telemetry_command('getAudioInDevices()')

    def get_preferred_mic(self):
        """Get preferred microphone for hotrod."""
        return self._evaluate_telemetry_command('getPreferredAudioInDevice()')

    def set_preferred_mic(self, mic_name):
        """Set preferred mic for hotrod.

        @param mic_name: String with mic name.
        """
        self._execute_telemetry_command('setPreferredAudioInDevice(%s)'
                                        % mic_name)
        logging.info('Setting preferred mic to %s.', mic_name)

    # Speaker commands/functions
    def get_speaker_devices(self):
        """Get all speaker devices detected by hotrod."""
        return self._evaluate_telemetry_command('getAudioOutDevices()')

    def get_preferred_speaker(self):
        """Get speaker preferred for hotrod."""
        return self._evaluate_telemetry_command('getPreferredAudioOutDevice()')

    def set_preferred_speaker(self, speaker_name):
        """Set preferred speaker for hotrod.

        @param speaker_name: String with speaker name.
        """
        self._execute_telemetry_command('setPreferredAudioOutDevice(%s)'
                                        % speaker_name)
        logging.info('Set preferred speaker to %s.', speaker_name)

    def set_speaker_volume(self, volume_level):
        """Set speaker volume.

        @param volume_level: Number value ranging from 0-100 to set volume to.
        """
        self._execute_telemetry_command('setAudioOutVolume(%d)' % volume_level)
        logging.info('Set speaker volume to %d', volume_level)

    def get_speaker_volume(self):
        """Get current speaker volume."""
        return self._evaluate_telemetry_command('getAudioOutVolume()')

    # Camera commands/functions
    def get_camera_devices(self):
        """Get all camera devices detected by hotrod.

        @return List of camera devices.
        """
        return self._evaluate_telemetry_command('getVideoInDevices()')

    def get_preferred_camera(self):
        """Get camera preferred for hotrod."""
        return self._evaluate_telemetry_command('getPreferredVideoInDevice()')

    def set_preferred_camera(self, camera_name):
        """Set preferred camera for hotrod.

        @param camera_name: String with camera name.
        """
        self._execute_telemetry_command('setPreferredVideoInDevice(%s)'
                                        % camera_name)
        logging.info('Set preferred camera to %s.', camera_name)

    def is_camera_muted(self):
        """Check if camera is muted (turned off)."""
        if self._evaluate_telemetry_command('isCameraMuted()'):
            logging.info('Camera is muted.')
            return True
        logging.info('Camera is not muted.')
        return False

    def mute_camera(self):
        """Mute (turn off) camera."""
        self._execute_telemetry_command('setCameraMuted(true)')
        logging.info('Camera muted.')

    def unmute_camera(self):
        """Unmute (turn on) camera."""
        self._execute_telemetry_command('setCameraMuted(false)')
        logging.info('Camera unmuted.')
