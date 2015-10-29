# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handler for audio extension functionality."""

from autotest_lib.client.bin import utils
from autotest_lib.client.cros.multimedia import facade_resource

class AudioExtensionHandlerError(Exception):
    pass


class AudioExtensionHandler(object):
    def __init__(self, extension):
        """Initializes an AudioExtensionHandler.

        @param extension: Extension got from telemetry chrome wrapper.

        """
        self._extension = extension
        self._check_api_available()


    def _check_api_available(self):
        """Checks chrome.audio is available."""
        success = utils.wait_for_value(
                lambda: (self._extension.EvaluateJavaScript(
                         "chrome.audio") != None),
                expected_value=True)
        if not success:
            raise AudioExtensionHandlerError('chrome.audio is not available.')


    @facade_resource.retry_chrome_call
    def get_audio_info(self):
        """Gets the audio info from Chrome audio API.

        @returns: An array of [outputInfo, inputInfo].
                  outputInfo is an array of output node info dicts. Each dict
                  contains these key-value pairs:
                     string  id
                         The unique identifier of the audio output device.

                     string  name
                         The user-friendly name (e.g. "Bose Amplifier").

                     boolean isActive
                         True if this is the current active device.

                     boolean isMuted
                         True if this is muted.

                     double  volume
                         The output volume ranging from 0.0 to 100.0.

                  inputInfo is an arrya of input node info dicts. Each dict
                  contains these key-value pairs:
                     string  id
                         The unique identifier of the audio input device.

                     string  name
                         The user-friendly name (e.g. "USB Microphone").

                     boolean isActive
                         True if this is the current active device.

                     boolean isMuted
                         True if this is muted.

                     double  gain
                         The input gain ranging from 0.0 to 100.0.

        """
        self._extension.ExecuteJavaScript('window.__audio_info = null;')
        self._extension.ExecuteJavaScript(
                "chrome.audio.getInfo(function(outputInfo, inputInfo) {"
                "window.__audio_info = [outputInfo, inputInfo];})")
        utils.wait_for_value(
                lambda: (self._extension.EvaluateJavaScript(
                         "window.__audio_info") != None),
                expected_value=True)
        return self._extension.EvaluateJavaScript("window.__audio_info")
