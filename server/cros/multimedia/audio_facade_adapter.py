# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An adapter to remotely access the audio facade on DUT."""

import os
import uuid


class AudioFacadeRemoteAdapter(object):
    """AudioFacadeRemoteAdapter is an adapter to remotely control DUT audio.

    The Autotest host object representing the remote DUT, passed to this
    class on initialization, can be accessed from its _client property.

    """
    def __init__(self, host, remote_facade_proxy):
        """Construct an AudioFacadeRemoteAdapter.

        @param host: Host object representing a remote host.
        @param remote_facade_proxy: RemoteFacadeProxy object.

        """
        self._client = host
        self._proxy = remote_facade_proxy


    @property
    def _audio_proxy(self):
        """Gets the proxy to DUT audio facade.

        @return XML RPC proxy to DUT audio facade.

        """
        return self._proxy.audio


    def playback(self, file_path, data_format, blocking=False):
        """Playback an audio file on DUT.

        @param file_path: The path to the file.
        @param data_format: A dict containing data format including
                            file_type, sample_format, channel, and rate.
                            file_type: file type e.g. 'raw' or 'wav'.
                            sample_format: One of the keys in
                                           audio_data.SAMPLE_FORMAT.
                            channel: number of channels.
                            rate: sampling rate.
        @param blocking: Blocks this call until playback finishes.

        @param returns: True

        """
        client_path = self._copy_file_to_client(file_path)
        self._audio_proxy.playback(
                client_path, data_format, blocking)


    def _copy_file_to_client(self, path):
        """Copy a file to client.

        @param path: A path to the file.

        @returns: A new path to the file on client.

        """
        _, ext = os.path.split(path)
        client_file_path = self._generate_client_temp_file_path(ext)
        self._client.send_file(path, client_file_path)
        return client_file_path


    def _generate_client_temp_file_path(self, ext):
        """Generates a temporary file path on client.

        @param ext: The extension of the file path.

        @returns: A temporary file path on client.

        """
        return os.path.join(
                '/tmp', 'audio_%s.%s' % (str(uuid.uuid4()), ext))
