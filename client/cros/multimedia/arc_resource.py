# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Resource manager to access the ARC-related functionality."""

import os
import pipes
import time

try:
    from autotest_lib.client.common_lib.cros import arc
except ImportError:
    from autotest_lib.client.common_lib.cros import arc_new as arc
from autotest_lib.client.cros.multimedia import arc_resource_common


def set_tag(tag):
    """Sets a tag file.

    @param tag: Path to the tag file.

    """
    open(tag, 'w').close()


def tag_exists(tag):
    """Checks if a tag exists.

    @param tag: Path to the tag file.

    """
    return os.path.exists(tag)


class ArcMicrophoneResourceException(Exception):
    """Exceptions in ArcResource."""
    pass


class ArcMicrophoneResource(object):
    """Class to manage microphone app in container."""
    _MICROPHONE_ACTIVITY = 'org.chromium.arc.testapp.microphone/.MainActivity'
    _MICROPHONE_PACKAGE = 'org.chromium.arc.testapp.microphone'
    _MICROPHONE_RECORD_PATH = '/storage/emulated/0/recorded.amr-nb'
    _MICROPHONE_PERMISSIONS = ['RECORD_AUDIO', 'WRITE_EXTERNAL_STORAGE',
                               'READ_EXTERNAL_STORAGE']

    def __init__(self):
        """Initializes a ArcMicrophoneResource."""
        self._mic_app_start_time = None


    def start_microphone_app(self):
        """Starts microphone app to start recording.

        Starts microphone app. The app starts recorder itself after start up.

        @raises: ArcMicrophoneResourceException if microphone app is not ready
                 yet.

        """
        if not tag_exists(arc_resource_common.MicrophoneProps.READY_TAG_FILE):
            raise ArcMicrophoneResourceException(
                    'Microphone app is not ready yet.')

        if self._mic_app_start_time:
            raise ArcMicrophoneResourceException(
                    'Microphone app is already started.')

        # In case the permissions are cleared, set the permission again before
        # each start of the app.
        self._set_permission()
        self._start_app()
        self._mic_app_start_time = time.time()


    def stop_microphone_app(self, dest_path):
        """Stops microphone app and gets recorded audio file from container.

        Stops microphone app.
        Copies the recorded file from container to Cros device.
        Deletes the recorded file in container.

        @dest_path: Destination path of the recorded file on Cros device.

        @raises: ArcMicrophoneResourceException if microphone app is not started
                 yet or is still recording.

        """
        if not self._mic_app_start_time:
            raise ArcMicrophoneResourceException(
                    'Recording is not started yet')

        if self._is_recording():
            raise ArcMicrophoneResourceException('Still recording')

        self._stop_app()
        self._get_file(dest_path)
        self._delete_file()

        self._mic_app_start_time = None


    def _is_recording(self):
        """Checks if microphone app is recording audio.

        We use the time stamp of app start up time to determine if app is still
        recording audio.

        @returns: True if microphone app is recording, False otherwise.

        """
        if not self._mic_app_start_time:
            return False

        return (time.time() - self._mic_app_start_time <
                (arc_resource_common.MicrophoneProps.RECORD_SECS +
                 arc_resource_common.MicrophoneProps.RECORD_FUZZ_SECS))


    def _set_permission(self):
        """Grants permissions to microphone app."""
        for permission in self._MICROPHONE_PERMISSIONS:
            arc.adb_shell('pm grant %s android.permission.%s' % (
                    pipes.quote(self._MICROPHONE_PACKAGE),
                    pipes.quote(permission)))


    def _start_app(self):
        """Starts microphone app."""
        arc.adb_shell('am start -W %s' % pipes.quote(self._MICROPHONE_ACTIVITY))


    def _stop_app(self):
        """Stops microphone app.

        Stops the microphone app process.

        """
        arc.adb_shell(
                'am force-stop %s' % pipes.quote(self._MICROPHONE_PACKAGE))


    def _get_file(self, dest_path):
        """Gets recorded audio file from container.

        Copies the recorded file from container to Cros device.

        @dest_path: Destination path of the recorded file on Cros device.

        """
        arc.adb_cmd('pull %s %s' % (pipes.quote(self._MICROPHONE_RECORD_PATH),
                                    pipes.quote(dest_path)))


    def _delete_file(self):
        """Removes the recorded file in container."""
        arc.adb_shell('rm %s' % pipes.quote(self._MICROPHONE_RECORD_PATH))


class ArcResource(object):
    """Class to manage multimedia resource in container.

    @properties:
        microphone: The instance of ArcMicrophoneResource for microphone app.

    """
    def __init__(self):
        self.microphone = ArcMicrophoneResource()
