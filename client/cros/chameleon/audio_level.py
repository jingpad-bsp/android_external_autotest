# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""This module provides the level control for audio widgets."""


from autotest_lib.client.cros.chameleon import chameleon_audio_ids as ids


class _AudioLevel(object):
    """Audio signal level on audio widgets."""
    # Line level signal on consumer equipment is typically -10 dBV, or
    # 0.316 Volt RMS.
    LINE_LEVEL = 'Line level'
    # Mic level signal on microphone is typically -60 dBV, or
    # 1 mV RMS.
    MIC_LEVEL = 'Mic level'
    # Digital signal, e.g., USB, HDMI. is not subjected to bias level or
    # full swing constraints. The signal is guranteed to be transmitted to the
    # other end without noise introduced on the path.
    # Signal level is relative to full swing of data width.
    # E.g. 2^12 is 1/8 of maximum amplitude, that is, 2^15 - 1, of signed
    # 16 bit data format.
    # TODO(cychiang) Check if we need to do level scaling for digital signal.
    DIGITAL = 'Digital'


_LEVEL_TABLE = {
        # Chameleon audio ports.
        ids.ChameleonIds.HDMI: _AudioLevel.DIGITAL,
        ids.ChameleonIds.LINEIN: _AudioLevel.LINE_LEVEL,
        ids.ChameleonIds.LINEOUT: _AudioLevel.LINE_LEVEL,
        # Cros audio ports.
        ids.CrosIds.HDMI: _AudioLevel.DIGITAL,
        ids.CrosIds.HEADPHONE: _AudioLevel.LINE_LEVEL,
        ids.CrosIds.EXTERNAL_MIC: _AudioLevel.MIC_LEVEL,
        ids.CrosIds.SPEAKER: _AudioLevel.LINE_LEVEL,
        ids.CrosIds.INTERNAL_MIC: _AudioLevel.MIC_LEVEL,
        # Peripheral audio ports.
        ids.PeripheralIds.SPEAKER: _AudioLevel.LINE_LEVEL,
        ids.PeripheralIds.MIC: _AudioLevel.MIC_LEVEL,
}


class AudioLevelError(Exception):
    """Error in _AudioLevel"""
    pass


def get_level(port_id):
    """Gets audio level by port id.

    @param port_id: An audio port id defined in ids.

    @returns: An audio level defined in _AudioLevel.

    """
    if port_id not in _LEVEL_TABLE:
        raise AudioLevelError('Level of port %s is not defined.' % port_id)
    return _LEVEL_TABLE[port_id]


class _AudioScale(object):
    """Audio scales used by level controller.

    The scales are determined by experiment.

    """
    DOWN_SCALE = 0.005
    UP_SCALE = 200.0
    NO_SCALE = None


class LevelControllerError(Exception):
    """Error in LevelController."""
    pass


class LevelController(object):
    """The controller which sets scale between widgets of different levels.

    Specifically, there are two cases:
    1. ChameleonIds.LINEOUT -> CrosIds.EXTERNAL_MIC: Chameleon scales down
       signal before playback.
    2. PeripheralIds.MIC -> ChameleonIds.LINEIN: Chameleon scales up signal
       after recording.

    """
    def __init__(self, source, sink):
        """Initializes a LevelController.

        @param source: An AudioWidget for source.
        @param sink: An AudioWidget for sink.

        """
        self._source = source
        self._sink = sink


    def _get_needed_scale(self):
        """Gets the needed scale for _source and _sink to balance the level.

        @returns: A scale defined in _AudioScale.

        """
        source_level = get_level(self._source.port_id)
        sink_level = get_level(self._sink.port_id)
        if (source_level == _AudioLevel.LINE_LEVEL and
            sink_level == _AudioLevel.MIC_LEVEL):
            return _AudioScale.DOWN_SCALE
        elif (source_level == _AudioLevel.MIC_LEVEL and
              sink_level == _AudioLevel.LINE_LEVEL):
            return _AudioScale.UP_SCALE
        return _AudioScale.NO_SCALE


    def _scale_source(self):
        """Sets scale of _source widget."""
        self._source.handler.scale = self._get_needed_scale()
        self._sink.handler.scale = _AudioScale.NO_SCALE


    def _scale_sink(self):
        """Sets scale of _sink widget."""
        self._source.handler.scale = _AudioScale.NO_SCALE
        self._sink.handler.scale = self._get_needed_scale()


    def reset(self):
        """Resets scale of both _source and _sink."""
        self._source.handler.scale = _AudioScale.NO_SCALE
        self._sink.handler.scale = _AudioScale.NO_SCALE


    def _support_scale(self, widget):
        """Checks if a widget supports scale.

        @param widget: An AudioWidget.

        @returns: True if the widget supports scale. False otherwise.

        """
        # Currently, only Chameleon supports scale.
        return widget.audio_port.host == 'Chameleon'


    def set_scale(self):
        """Sets scale of either _source or _sink to balance the level.

        @raises: LevelControllerError if neither _source nor _sink supports
                 scale.

        """
        if self._support_scale(self._source):
            self._scale_source()
        elif self._support_scale(self._sink):
            self._scale_sink()
        elif self._get_needed_scale != _AudioScale.NO_SCALE:
            raise LevelControllerError(
                    'Widgets %s and %s do not support scale' % (
                    self._source.audio_port, self._sink.audio_port))
