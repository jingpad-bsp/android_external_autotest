# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class AudioClient(object):
    """AudioClient is a layer to control audio logic over a remote DUT."""
    def __init__(self, multimedia_client_connection):
        """Construct an AudioClient.

        @param multimedia_client_connection: MultimediaClientConnection object.
        """
        self._connection = multimedia_client_connection

    @property
    def _audio_proxy(self):
        """Gets the proxy to DUT audio utility.

        @return XML RPC proxy to DUT audio utility.
        """
        return self._connection.xmlrpc_proxy.audio

    def playback(self, file_path):
        """Playback an audio file on DUT.

        @param file_path: The path to the file on DUT.
        """
        self._audio_proxy.playback(file_path)
