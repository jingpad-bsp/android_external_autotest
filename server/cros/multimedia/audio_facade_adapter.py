# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An adapter to remotely access the audio facade on DUT."""

import os
import tempfile


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


    def playback(self, client_path, data_format, blocking=False):
        """Playback an audio file on DUT.

        @param client_path: The path to the file on DUT.
        @param data_format: A dict containing data format including
                            file_type, sample_format, channel, and rate.
                            file_type: file type e.g. 'raw' or 'wav'.
                            sample_format: One of the keys in
                                           audio_data.SAMPLE_FORMAT.
                            channel: number of channels.
                            rate: sampling rate.
        @param blocking: Blocks this call until playback finishes.

        @returns: True

        """
        self._audio_proxy.playback(
                client_path, data_format, blocking)


    def set_playback_file(self, path):
        """Copies a file to client.

        @param path: A path to the file.

        @returns: A new path to the file on client.

        """
        _, ext = os.path.splitext(path)
        _, client_file_path = tempfile.mkstemp(
                prefix='playback_', suffix=ext)
        self._client.send_file(path, client_file_path)
        return client_file_path


    def start_recording(self, data_format):
        """Starts recording an audio file on DUT.

        @param data_format: A dict containing:
                            file_type: 'raw'.
                            sample_format: 'S16_LE' for 16-bit signed integer in
                                           little-endian.
                            channel: channel number.
                            rate: sampling rate.

        @returns: True

        """
        self._audio_proxy.start_recording(data_format)
        return True


    def stop_recording(self):
        """Stops recording on DUT.

        @returns: the path to the recorded file on DUT.

        """
        return self._audio_proxy.stop_recording()


    def get_recorded_file(self, remote_path, local_path):
        """Gets a recorded file from DUT.

        @param remote_path: The path to the file on DUT.
        @param local_path: The local path for copy destination.

        """
        self._client.get_file(remote_path, local_path)


    def set_selected_output_volume(self, volume):
        """Sets the selected output volume on DUT.

        @param volume: the volume to be set(0-100).

        """
        self._audio_proxy.set_selected_output_volume(volume)


    def get_selected_node_types(self):
        """Gets the selected output and input node types on DUT.

        @returns: A tuple (output_node_types, input_node_types) where each
                  field is a list of selected node types defined in
                  cras_utils.CRAS_NODE_TYPES.

        """
        return self._audio_proxy.get_selected_node_types()


    def dump_diagnostics(self, file_path):
        """Dumps audio diagnostics results to a file.

        @param file_path: The path to dump results.

        @returns: True

        """
        _, remote_path = tempfile.mkstemp(
                prefix='audio_dump_', suffix='.txt')
        self._audio_proxy.dump_diagnostics(remote_path)
        self._client.get_file(remote_path, file_path)
        return True
