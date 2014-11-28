# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Facade to access the audio-related functionality."""

import logging
import multiprocessing

from autotest_lib.client.cros.audio import cras_utils


class AudioFacadeNative(object):
    """Facede to access the audio-related functionality.

    The methods inside this class only accept Python native types.

    """

    def __init__(self, chrome):
        self._chrome = chrome
        self._browser = chrome.browser


    def playback(self, file_path, blocking=False):
        """Playback a file.

        @param file_path: The path to the file.
        @param blocking: Blocks this call until playback finishes.

        """
        logging.debug('AudioFacadeNative playback file %s', file_path)

        def _playback():
            """Playback using cras utility."""
            cras_utils.playback(playback_file=file_path)

        if blocking:
            _playback()
        else:
            p = multiprocessing.Process(target=_playback)
            p.daemon=True
            p.start()

        return True
