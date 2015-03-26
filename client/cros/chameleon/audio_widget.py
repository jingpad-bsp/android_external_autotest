# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides the audio widgets used in audio tests."""

import abc
import copy
import logging
import tempfile

from autotest_lib.client.cros.audio import audio_data
from autotest_lib.client.cros.audio import audio_test_data
from autotest_lib.client.cros.audio import sox_utils
from autotest_lib.client.cros.chameleon import chameleon_port_finder


class AudioWidget(object):
    """
    This class abstracts an audio widget in audio test framework. A widget
    is identified by its audio port. The handler passed in at __init__ will
    handle action on the audio widget.

    Properties:
        audio_port: The AudioPort this AudioWidget resides in.
        handler: The handler that handles audio action on the widget. It is
                  actually a (Chameleon/Cros)(Input/Output)WidgetHandler object.

    """
    def __init__(self, audio_port, handler):
        """Initializes an AudioWidget on a AudioPort.

        @param audio_port: An AudioPort object.
        @param handler: A WidgetHandler object which handles action on the widget.

        """
        self.audio_port = audio_port
        self.handler = handler


    @property
    def port_id(self):
        """Port id of this audio widget.

        @returns: A string. The port id defined in chameleon_audio_ids for this
                  audio widget.
        """
        return self.audio_port.port_id


class AudioInputWidget(AudioWidget):
    """
    This class abstracts an audio input widget. This class provides the audio
    action that is available on an input audio port.

    Properties:
        _rec_binary: The recorded binary data.
        _rec_format: The recorded data format. A dict containing
                     file_type: 'raw' or 'wav'.
                     sample_format: 'S32_LE' for 32-bit signed integer in
                                    little-endian. Refer to aplay manpage for
                                    other formats.
                     channel: channel number.
                     rate: sampling rate.

        _channel_map: A list containing current channel map. Checks docstring
                      of channel_map method for details.

    """
    def __init__(self, *args, **kwargs):
        """Initializes an AudioInputWidget."""
        super(AudioInputWidget, self).__init__(*args, **kwargs)
        self._rec_binary = None
        self._rec_format = None
        self._channel_map = None


    def start_recording(self):
        """Starts recording."""
        self._rec_binary = None
        self._rec_format = None
        self.handler.start_recording()


    def stop_recording(self):
        """Stops recording."""
        self._rec_binary, self._rec_format = self.handler.stop_recording()


    def save_file(self, file_path):
        """Saves recorded data to a file.

        @param file_path: The path to save the file.

        """
        with open(file_path, 'wb') as f:
            logging.debug('Saving recorded raw file to %s', file_path)
            f.write(self._rec_binary)


    def get_binary(self):
        """Gets recorded binary data.

        @returns: The recorded binary data.

        """
        return self._rec_binary


    @property
    def data_format(self):
        """The recorded data format.

        @returns: The recorded data format.

        """
        return self._rec_format


    @property
    def channel_map(self):
        """The recorded data channel map.

        @returns: The recorded channel map. A list containing channel mapping.
                  E.g. [1, 0, None, None, None, None, None, None] means
                  channel 0 of recorded data should be mapped to channel 1 of
                  data played to the recorder. Channel 1 of recorded data should
                  be mapped to channel 0 of data played to recorder.
                  Channel 2 to 7 of recorded data should be ignored.

        """
        return self._channel_map


    @channel_map.setter
    def channel_map(self, new_channel_map):
        """Sets channel map.

        @param new_channel_map: A list containing new channel map.

        """
        self._channel_map = copy.deepcopy(new_channel_map)


    @property
    def _sample_size_bytes(self):
        """Gets sample size in bytes of recorded data."""
        return audio_data.SAMPLE_FORMATS[
                self._rec_format['sample_format']]['size_bytes']


    @property
    def _sample_size_bits(self):
        """Gets sample size in bits of recorded data."""
        return self._sample_size_bytes * 8


    @property
    def _channel(self):
        """Gets number of channels of recorded data."""
        return self._rec_format['channel']


    @property
    def _sampling_rate(self):
        """Gets sampling rate of recorded data."""
        return self._rec_format['rate']


    def remove_head(self, duration_secs):
        """Removes a duration of recorded data from head.

        @param duration_secs: The duration in seconds to be removed from head.

        """
        offset = int(self._sampling_rate * duration_secs *
                     self._sample_size_bytes * self._channel)
        self._rec_binary = self._rec_binary[offset:]


    def lowpass_filter(self, frequency):
        """Passes the recorded data to a lowpass filter.

        @param frequency: The 3dB frequency of lowpass filter.

        """
        with tempfile.NamedTemporaryFile(
                prefix='original_') as original_file:
            with tempfile.NamedTemporaryFile(
                    prefix='filtered_') as filtered_file:

                original_file.write(self._rec_binary)
                original_file.flush()

                sox_utils.lowpass_filter(
                        original_file.name, self._channel,
                        self._sample_size_bits, self._sampling_rate,
                        filtered_file.name, frequency)

                self._rec_binary = filtered_file.read()


class AudioOutputWidget(AudioWidget):
    """
    This class abstracts an audio output widget. This class provides the audio
    action that is available on an output audio port.

    """
    def start_playback(self, test_data, blocking=False):
        """Starts playing audio.

        @param test_data: An AudioTestData object.
        @param blocking: Blocks this call until playback finishes.
        """
        self.handler.start_playback(test_data, blocking)


    def stop_playback(self):
        """Stops playing audio."""
        self.handler.stop_playback()


class WidgetHandler(object):
    """This class abstracts handler for basic actions on widget."""
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def plug(self):
        """Plug this widget."""
        pass


    @abc.abstractmethod
    def unplug(self):
        """Unplug this widget."""
        pass


class ChameleonWidgetHandler(WidgetHandler):
    """
    This class abstracts a Chameleon audio widget handler.

    Properties:
        interface: A string that represents the interface name on
                   Chameleon, e.g. 'HDMI', 'LineIn', 'LineOut'.
        scale: The scale is the scaling factor to be applied on the data of the
               widget before playing or after recording.
        _chameleon_board: A ChameleonBoard object to control Chameleon.
        _port: A ChameleonPort object to control port on Chameleon.

    """
    def __init__(self, chameleon_board, interface):
        """Initializes a ChameleonWidgetHandler.

        @param chameleon_board: A ChameleonBoard object.
        @param interface: A string that represents the interface name on
                          Chameleon, e.g. 'HDMI', 'LineIn', 'LineOut'.

        """
        self.interface = interface
        self._chameleon_board = chameleon_board
        self._port = self._find_port(interface)
        self.scale = None


    @abc.abstractmethod
    def _find_port(self, interface):
        """Finds the port by interface."""
        pass


    def plug(self):
        """Plugs this widget."""
        self._port.plug()


    def unplug(self):
        """Unplugs this widget."""
        self._port.unplug()


class ChameleonInputWidgetHandler(ChameleonWidgetHandler):
    """
    This class abstracts a Chameleon audio input widget handler.

    """
    def start_recording(self):
        """Starts recording."""
        self._port.start_capturing_audio()


    def stop_recording(self):
        """Stops recording.

        Gets recorded binary and format from Chameleon. Also, handle scaling
        if needed.

        @returns: A tuple (data_binary, data_format) for recorded data.
                  Refer to stop_capturing_audio call of ChameleonAudioInput.

        """
        with tempfile.NamedTemporaryFile(prefix='recorded_') as f:
            # Gets recorded data and format by Chameleon port.
            rec_binary, rec_format = self._port.stop_capturing_audio()

            # Handles scaling using audio_test_data.
            open(f.name, 'w').write(rec_binary)
            test_data = audio_test_data.AudioTestData(rec_format, f.name)
            converted_test_data = test_data.convert(
                    rec_format, self.scale)
            scaled_binary = converted_test_data.get_binary()
            converted_test_data.delete()

            return scaled_binary, rec_format


    def _find_port(self, interface):
        """Finds a Chameleon audio port by interface(port name).

        @param interface: string, the interface. e.g: HDMI.

        @returns: A ChameleonPort object.

        @raises: ValueError if port is not connected.

        """
        finder = chameleon_port_finder.ChameleonAudioInputFinder(
                self._chameleon_board)
        chameleon_port = finder.find_port(interface)
        if not chameleon_port:
            raise ValueError(
                    'Port %s is not connected to Chameleon' % interface)
        return chameleon_port


class ChameleonOutputWidgetHandler(ChameleonWidgetHandler):
    """
    This class abstracts a Chameleon audio output widget handler.

    """
    _DEFAULT_DATA_FORMAT = dict(file_type='raw',
                                sample_format='S32_LE',
                                channel=8,
                                rate=48000)

    def start_playback(self, test_data, blocking=False):
        """Starts playback.

        @param test_data: An AudioTestData object.
        @param blocking: Blocks this call until playback finishes.

        """
        if blocking:
            raise NotImplementedError(
                    'Blocking playback on chameleon is not supported')

        converted_audio_test_data = test_data.convert(
                self._DEFAULT_DATA_FORMAT, self.scale)

        self._port.start_playing_audio(
                converted_audio_test_data.get_binary(),
                self._DEFAULT_DATA_FORMAT)

        converted_audio_test_data.delete()


    def stop_playback(self):
        """Stops playback."""
        self._port.stop_playing_audio()


    def _find_port(self, interface):
        """Finds a Chameleon audio port by interface(port name).

        @param interface: string, the interface. e.g: LineOut.

        @returns: A ChameleonPort object.

        @raises: ValueError if port is not connected.

        """
        finder = chameleon_port_finder.ChameleonAudioOutputFinder(
                self._chameleon_board)
        chameleon_port = finder.find_port(interface)
        if not chameleon_port:
            raise ValueError(
                    'Port %s is not connected to Chameleon' % interface)
        return chameleon_port


class CrosWidgetHandler(WidgetHandler):
    """
    This class abstracts a Cros device audio widget handler.

    Properties:
        _audio_facade: An AudioFacadeRemoteAdapter to access Cros device
                       audio functionality.

    """
    def __init__(self, audio_facade):
        """Initializes a CrosWidgetHandler.

        @param audio_facade: An AudioFacadeRemoteAdapter to access Cros device
                             audio functionality.

        """
        self._audio_facade = audio_facade


    def plug(self):
        """Plugs this widget."""
        # TODO(cychiang): Implement plug control. This class
        # will need access to ChameleonBoard and interface name.
        # For widget on 3.5mm jack(Headphone and External Mic), we need to
        # plug/unplug 3.5mm jack by fixture controlled by Chameleon.
        pass


    def unplug(self):
        """Unplugs this widget."""
        # TODO(cychiang): Similar to plug().
        pass


class CrosInputWidgetHandler(CrosWidgetHandler):
    """
    This class abstracts a Cros device audio input widget handler.

    """
    _DEFAULT_DATA_FORMAT = dict(file_type='raw',
                                sample_format='S16_LE',
                                channel=1,
                                rate=48000)

    def start_recording(self):
        """Starts recording audio."""
        self._audio_facade.start_recording(self._DEFAULT_DATA_FORMAT)


    def stop_recording(self):
        """Stops recording audio.

        @returns:
            A tuple (data, format).
                data: The recorded binary data.
                format: A dict containing:
                    file_type: 'raw'.
                    sample_format: 'S16_LE' for 16-bit signed integer in
                                   little-endian.
                    channel: channel number.
                    rate: sampling rate.

        """
        with tempfile.NamedTemporaryFile(prefix='recorded_', delete=False) as f:
            self._audio_facade.stop_recording(f.name)
            return open(f.name).read(), self._DEFAULT_DATA_FORMAT


class CrosOutputWidgetHandlerError(Exception):
    """The error in CrosOutputWidgetHandler."""
    pass


class CrosOutputWidgetHandler(CrosWidgetHandler):
    """
    This class abstracts a Cros device audio output widget handler.

    """
    _DEFAULT_DATA_FORMAT = dict(file_type='raw',
                                sample_format='S16_LE',
                                channel=2,
                                rate=48000)

    def start_playback(self, test_data, blocking=False):
        """Starts playing audio.

        @param test_data: An AudioTestData object.
        @param blocking: Blocks this call until playback finishes.

        """
        # TODO(cychiang): Do format conversion on Cros device if this is
        # needed.
        if test_data.data_format != self._DEFAULT_DATA_FORMAT:
            raise CrosOutputWidgetHandlerError(
                    'File format conversion for cros device is not supported.')

        return self._audio_facade.playback(test_data.path, test_data.data_format,
                                           blocking)


    def stop_playback(self):
        """Stops playing audio."""
        raise NotImplementedError


class PeripheralWidgetHandler(object):
    """
    This class abstracts an action handler on peripheral.
    Currently, as there is no action to take on the peripheral speaker and mic,
    this class serves as a place-holder.

    """
    pass
