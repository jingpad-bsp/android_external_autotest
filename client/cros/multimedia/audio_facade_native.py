# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Facade to access the audio-related functionality."""

import logging
import multiprocessing

from autotest_lib.client.cros.audio import cras_utils


class AudioFacadeNativeError(Exception):
    """Error in AudioFacadeNative."""
    pass


class AudioFacadeNative(object):
    """Facede to access the audio-related functionality.

    The methods inside this class only accept Python native types.

    """

    _PLAYBACK_DATA_FORMAT = dict(
            file_type='raw', sample_format='S16_LE', channel=2, rate=48000)

    def __init__(self, chrome):
        self._chrome = chrome
        self._browser = chrome.browser


    def playback(self, file_path, data_format, blocking=False):
        """Playback a file.

        @param file_path: The path to the file.
        @param data_format: A dict containing data format including
                            file_type, sample_format, channel, and rate.
                            file_type: file type e.g. 'raw' or 'wav'.
                            sample_format: One of the keys in
                                           audio_data.SAMPLE_FORMAT.
                            channel: number of channels.
                            rate: sampling rate.
        @param blocking: Blocks this call until playback finishes.

        @returns: True.

        @raises: AudioFacadeNativeError if data format is not supported.

        """
        logging.info('AudioFacadeNative playback file: %r. format: %r',
                     file_path, data_format)

        if data_format != self._PLAYBACK_DATA_FORMAT:
            raise AudioFacadeNativeError(
                    'data format %r is not supported' % data_format)

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
