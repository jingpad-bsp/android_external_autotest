# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides the audio widgets used in audio tests."""

import abc
import logging

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

    """
    def __init__(self, *args, **kwargs):
        """Initializes an AudioInputWidget."""
        super(AudioInputWidget, self).__init__(*args, **kwargs)
        self._rec_binary = None
        self._rec_format = None


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
        return self.handler.channel_map


class AudioOutputWidget(AudioWidget):
    """
    This class abstracts an audio output widget. This class provides the audio
    action that is available on an output audio port.

    """
    def start_playback(self, file_path):
        """Starts playing audio.

        @param file_path: Path to the file to play.
        """
        self.handler.start_playback(file_path)


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
    # This is the default channel map for 2-channel data recorded on
    # Chameleon.
    _DEFAULT_CHANNEL_MAP = [1, 0, None, None, None, None, None, None]

    def start_recording(self):
        """Starts recording."""
        self._port.start_capturing_audio()


    def stop_recording(self):
        """Stops recording.

        @returns: A tuple (data_binary, data_format) for recorded data.
                  Refer to stop_capturing_audio call of ChameleonAudioInput.

        """
        return self._port.stop_capturing_audio()


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


    @property
    def channel_map(self):
        """Returns the channel map used by this handler.

        @returns: The default channel map.

        """
        # TODO(cychiang): Support multi-channel channel map.
        return self._DEFAULT_CHANNEL_MAP


class ChameleonOutputWidgetHandler(ChameleonWidgetHandler):
    """
    This class abstracts a Chameleon audio output widget handler.

    """
    # TODO(cychiang): Add Chameleon audio output port.
    def start_playback(self, file_path):
        """Starts playback.

        @param file_path: Path to the file to play.

        """
        raise NotImplementedError


    def stop_playback(self):
        """Stops playback."""
        raise NotImplementedError


    def _find_port(self, interface):
        """Finds a Chameleon audio port by interface(port name).

        @param interface: string, the interface. e.g: LineOut.

        @returns: A ChameleonPort object.

        @raises: ValueError if port is not connected.

        """
        raise NotImplementedError


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
    def start_recording(self):
        """Starts recording audio."""
        raise NotImplementedError


    def stop_recording(self):
        """Stops recording audio."""
        raise NotImplementedError


class CrosOutputWidgetHandler(CrosWidgetHandler):
    """
    This class abstracts a Cros device audio output widget handler.

    """
    def start_playback(self, file_path):
        """Starts playing audio.

        @param file_path: Path to the file to play.

        """
        return self._audio_facade.playback(file_path)


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
