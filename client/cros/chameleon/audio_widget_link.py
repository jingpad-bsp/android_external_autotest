# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides the link between audio widgets."""

import abc
import logging

from autotest_lib.client.cros.chameleon import chameleon_audio_ids as ids


class WidgetBinderError(Exception):
    """Error in WidgetBinder."""
    pass


class WidgetBinder(object):
    """
    This class abstracts the binding controls between two audio widgets.

     ________          __________________          ______
    |        |        |      link        |        |      |
    | source |------->| input     output |------->| sink |
    |________|        |__________________|        |______|

    Properties:
        _source: An AudioWidget object. The audio source. This should be
                 an output widget.
        _sink: An AudioWidget object. The audio sink. This should be an
                 input widget.
        _link: An WidgetLink object to link source and sink.
        _connected: True if this binder is connected.
    """
    def __init__(self, source, link, sink):
        """Initializes a WidgetBinder.

        After initialization, the binder is not connected, but the link
        is occupied until it is released.
        After connection, the channel map of link will be set to the sink
        widget, and it will remains the same until the sink widget is connected
        to a different link. This is to make sure sink widget knows the channel
        map of recorded data even after link is disconnected or released.

        @param source: An AudioWidget object for audio source.
        @param link: A WidgetLink object to connect source and sink.
        @param sink: An AudioWidget object for audio sink.

        """
        self._source = source
        self._link = link
        self._sink = sink
        self._connected = False
        self._link.occupied = True


    def connect(self):
        """Connects source and sink to link."""
        if self._connected:
            return

        logging.info('Connecting %s to %s', self._source.audio_port,
                     self._sink.audio_port)
        self._link.plug_input(self._source)
        self._link.plug_output(self._sink)
        self._connected = True
        # Sets channel map of link to the sink widget so
        # sink widget knows the channel map of recorded data.
        self._sink.channel_map = self._link.channel_map


    def disconnect(self):
        """Disconnects source and sink from link."""
        if not self._connected:
            return

        logging.info('Disconnecting %s to %s', self._source.audio_port,
                     self._sink.audio_port)
        self._link.unplug_input(self._source)
        self._link.unplug_output(self._sink)
        self._connected = False


    def release(self):
        """Releases the link used by this binder.

        @raises: WidgetBinderError if this binder is still connected.

        """
        if self._connected:
            raise WidgetBinderError('Can not release while connected')
        self._link.occupied = False


class WidgetLinkError(Exception):
    """Error in WidgetLink."""
    pass


class WidgetLink(object):
    """
    This class abstracts the link between two audio widgets.

    Properties:
        name: A string. The link name.
        occupied: True if this widget is occupied by a widget binder.
        channel_map: A list containing current channel map. Checks docstring
                     of channel_map method of AudioInputWidget for details.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.name = 'Unknown'
        self.occupied = False
        self.channel_map = None


    def _check_widget_id(self, port_id, widget):
        """Checks that the port id of a widget is expected.

        @param port_id: An id defined in chameleon_audio_ids.
        @param widget: An AudioWidget object.

        @raises: WidgetLinkError if the port id of widget is not expected.
        """
        if widget.audio_port.port_id != port_id:
            raise WidgetLinkError(
                    'Link %s expects a %s widget, but gets a %s widget' % (
                            self.name, port_id, widget.audio_port.port_id))


    def _check_widget_direction(self, direction, widget):
        """Checks that the direction of a widget is expected.

        @param direction: 'Input' or 'Output'.
        @param widget: An AudioWidget object.

        @raises: WidgetLinkError if the direction of widget is not expected.
        """
        if widget.audio_port.direction != direction:
            raise WidgetLinkError(
                    'Link %s expects a %s widget, but gets a %s widget' % (
                            self.name, direction, widget.audio_port.direction))


    @abc.abstractmethod
    def plug_input(self, widget):
        """Plugs input of this link to the widget.

        @param widget: An AudioWidget object.

        """
        pass


    @abc.abstractmethod
    def unplug_input(self, widget):
        """Unplugs input of this link from the widget.

        @param widget: An AudioWidget object.

        """
        pass


    @abc.abstractmethod
    def plug_output(self, widget):
        """Plugs output of this link to the widget.

        @param widget: An AudioWidget object.

        """
        pass


    @abc.abstractmethod
    def unplug_output(self, widget):
        """Unplugs output of this link from the widget.

        @param widget: An AudioWidget object.

        """
        pass


class AudioBusLink(WidgetLink):
    """The abstraction for bus on audio board.

    Properties:
        bus_index: The bus index on audio board.
    """
    def __init__(self, bus_index):
        super(AudioBusLink, self).__init__()
        self.bus_index = bus_index
        logging.debug(
                'Create an AudioBusLink with bus '
                'index %d', bus_index)


    def plug_input(self, widget):
        """Plugs input of audio bus to the widget.

        @param widget: An AudioWidget object.

        """
        # TODO(cychiang) Implement audio board path control to connect
        # audio port of widget to bus input. This would be done through
        # a chameleon_board object passed in by AudioWidgetFactory.
        # e.g. self.chameleon_board.audio_board.connect_audio_bus(
        #              self.bus_index, widget.audio_port.port_id)

        # TODO(cychiang) Implement fixture control to plug 3.5mm jack if
        # widget is on Cros device and it is not plugged yet.
        # e.g. self.chameleon_board.audio_board.plug_audio_jack()
        self._check_widget_direction('Output', widget)
        logging.info(
                'Plug audio board bus %d input to %s',
                self.bus_index, widget.audio_port)


    def unplug_input(self, widget):
        """Unplugs input of audio bus to the widget.

        @param widget: An AudioWidget object.

        """
        # TODO(cychiang) Implement fixture control to unplug 3.5mm jack if
        # widget is on Cros device and both headphone and external mic are not
        # used.
        # We might need an argument here to decide to unplug 3.5mm jack or not.
        # e.g. self.chameleon_board.audio_board.unplug_audio_jack()

        # TODO(cychiang) Implement audio board path control to disconnect
        # audio port of widget from bus input. This would be done through
        # a chameleon_board object passed in by AudioWidgetFactory.
        # e.g. self.chameleon_board.audio_board.disconnect_audio_bus(
        #              self.bus_index, widget.audio_port.port_id)
        self._check_widget_direction('Output', widget)
        logging.info(
                'Unplug audio board bus %d input from %s',
                self.bus_index, widget.audio_port)


    def plug_output(self, widget):
        """Plugs output of audio bus to the widget.

        @param widget: An AudioWidget object.

        """
        # TODO(cychiang) Implement audio board path control to connect
        # audio port of widget to bus output. This would be done through
        # a chameleon_board object passed in by AudioWidgetFactory.
        # e.g. self.chameleon_board.audio_board.connect_audio_bus(
        #              self.bus_index, widget.audio_port.port_id)

        # TODO(cychiang) Implement fixture control to plug 3.5mm jack if
        # widget is on Cros device and it is not plugged yet.
        # e.g. self.chameleon_board.audio_board.plug_audio_jack()
        self._check_widget_direction('Input', widget)
        logging.info(
                'Plug audio board bus %d output to %s',
                self.bus_index, widget.audio_port)


    def unplug_output(self, widget):
        """Plugs output of audio bus to the widget.

        @param widget: An AudioWidget object.

        """
        # TODO(cychiang) Implement fixture control to unplug 3.5mm jack if
        # widget is on Cros device and both headphone and external mic are not
        # used.
        # We might need an argument here to decide to unplug 3.5mm jack or not.
        # e.g. self.chameleon_board.audio_board.unplug_audio_jack()

        # TODO(cychiang) Implement audio board path control to disconnect
        # audio port of widget from bus input. This would be done through
        # a chameleon_board object passed in by AudioWidgetFactory.
        # e.g. self.chameleon_board.audio_board.disconnect_audio_bus(
        #              self.bus_index, widget.audio_port.port_id)
        self._check_widget_direction('Input', widget)
        logging.info(
                'Unplug audio board bus %d output from %s',
                self.bus_index, widget.audio_port)


class AudioBusToChameleonLink(AudioBusLink):
    """The abstraction for bus on audio board that is connected to Chameleon."""
    # This is the default channel map for 2-channel data recorded on
    # Chameleon through audio board.
    _DEFAULT_CHANNEL_MAP = [0, 1, None, None, None, None, None, None]

    def __init__(self, *args, **kwargs):
        super(AudioBusToChameleonLink, self).__init__(
            *args, **kwargs)
        self.name = 'Audio board bus %s to Chameleon' % self.bus_index
        self.channel_map = self._DEFAULT_CHANNEL_MAP
        logging.debug(
                'Create an AudioBusToChameleonLink named %s with '
                'channel map %r', self.name, self.channel_map)


class HDMIWidgetLink(WidgetLink):
    """The abstraction for HDMI cable."""

    # This is the default channel map for 2-channel data recorded on
    # Chameleon through HDMI cable.
    _DEFAULT_CHANNEL_MAP = [1, 0, None, None, None, None, None, None]

    def __init__(self):
        super(HDMIWidgetLink, self).__init__()
        self.name = 'HDMI cable'
        self.channel_map = self._DEFAULT_CHANNEL_MAP
        logging.debug(
                'Create an HDMIWidgetLink. Do nothing because HDMI cable'
                ' is dedicated')


    def plug_input(self, widget):
        """Plugs input of HDMI cable to the widget using widget handler.

        @param widget: An AudioWidget object.

        """
        self._check_widget_id(ids.CrosIds.HDMI, widget)
        logging.info(
                'Plug HDMI cable input. Do nothing because HDMI cable should '
                'always be physically plugged to Cros device')


    def unplug_input(self, widget):
        """Unplugs input of HDMI cable from the widget using widget handler.

        @param widget_handler: A WidgetHandler object.

        """
        self._check_widget_id(ids.CrosIds.HDMI, widget)
        logging.info(
                'Unplug HDMI cable input. Do nothing because HDMI cable should '
                'always be physically plugged to Cros device')


    def plug_output(self, widget):
        """Plugs output of HDMI cable to the widget using widget handler.

        @param widget: An AudioWidget object.

        @raises: WidgetLinkError if widget handler interface is not HDMI.
        """
        self._check_widget_id(ids.ChameleonIds.HDMI, widget)
        # HDMI plugging emulation is done on Chameleon port.
        logging.info(
                'Plug HDMI cable output. This is emulated on Chameleon port')
        widget.handler.plug()


    def unplug_output(self, widget):
        """Unplugs output of HDMI cable from the widget using widget handler.

        @param widget: An AudioWidget object.

        @raises: WidgetLinkError if widget handler interface is not HDMI.
        """
        self._check_widget_id(ids.ChameleonIds.HDMI, widget)
        # HDMI plugging emulation is done on Chameleon port.
        logging.info(
                'Unplug HDMI cable output. This is emulated on Chameleon port')
        widget.handler.unplug()
