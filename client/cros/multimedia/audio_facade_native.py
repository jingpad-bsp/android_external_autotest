# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Facade to access the audio-related functionality."""

import logging

from autotest_lib.client.cros.audio import cras_utils


class AudioFacadeNative(object):
    """Facede to access the audio-related functionality.

    The methods inside this class only accept Python native types.
    """

    def __init__(self, chrome):
        self._chrome = chrome
        self._browser = chrome.browser

    def playback(self, file_path):
        """Playback a file.

        @param file_path: The path to the file.
        """
        logging.debug('AudioFacadeNative playback file %s', file_path)
        cras_utils.playback(playback_file=file_path)
        return True
