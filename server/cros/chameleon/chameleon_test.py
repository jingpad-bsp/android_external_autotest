# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import chameleon_port_finder
from autotest_lib.client.cros.chameleon import screen_test
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class ChameleonTest(test.test):
    """This is the base class of Chameleon tests.

    This base class initializes Chameleon board and its related services,
    like connecting Chameleond and DisplayFacade. Also kills the connections
    on cleanup.
    """

    _TIMEOUT_VIDEO_STABLE_PROBE = 10

    def initialize(self, host):
        """Initializes.

        @param host: The Host object of DUT.
        """
        factory = remote_facade_factory.RemoteFacadeFactory(host)
        self.audio_facade = factory.create_audio_facade()
        self.display_facade = factory.create_display_facade()
        self.chameleon = host.chameleon
        self.host = host
        # TODO(waihong): Support multiple connectors.
        self.chameleon_port = self._get_connected_port()
        self.screen_test = screen_test.ScreenTest(
                self.chameleon_port, self.display_facade, self.outputdir)
        self._platform_prefix = host.get_platform().lower().split('_')[0]


    def is_edid_supported(self, tag, width, height):
        """Check whether the EDID is supported by DUT

        @param tag: The tag of the EDID file; 'HDMI' or 'DP'
        @param width: The screen width
        @param height: The screen height

        @return: True if the check passes; False otherwise.
        """
        # TODO: This is a quick workaround; some of our arm devices so far only
        # support the HDMI EDIDs and the DP one at 1680x1050. A more proper
        # solution is to build a database of supported resolutions and pixel
        # clocks for each model and check if the EDID is in the supported list.
        if self._platform_prefix in ('snow', 'spring', 'skate', 'peach'):
            if tag == 'DP':
                return width == 1680 and height == 1050
        return True


    def cleanup(self):
        """Cleans up."""
        # Unplug the Chameleon port, not to affect other test cases.
        if hasattr(self, 'chameleon_port') and self.chameleon_port:
            self.chameleon_port.unplug()


    def _get_connected_port(self):
        """Gets the first connected output port between Chameleon and DUT.

        This method also plugs this port at the end.

        @return: A ChameleonPort object.
        """
        self.chameleon.reset()
        finder = chameleon_port_finder.ChameleonVideoInputFinder(
                self.chameleon, self.display_facade)
        ports = finder.find_all_ports()
        if len(ports.connected) == 0:
            raise error.TestError('DUT and Chameleon board not connected')
        # Plug the first port and return it.
        first_port = ports.connected[0]
        first_port.plug()
        first_port.wait_video_input_stable(self._TIMEOUT_VIDEO_STABLE_PROBE)
        return first_port


    def audio_start_recording(self, host, port):
        """Starts recording audio on a host using a port.

        @param host: The host to start recording. E.g. 'Chameleon' or 'DUT'.
                     Currently only 'Chameleon' is supported.
        @param port: The port to record audio. Currently only 'HDMI' is
                     supported.

        @returns: It depends on start_capturing_audio implementation on
                  different host and port.

        @raises: NotImplementedError if host/port is not supported.
        """
        if host == 'Chameleon':
            if port != self.chameleon_port.get_connector_type():
                raise ValueError(
                        'Port %s is not connected to Chameleon.' % port)
            if port == 'HDMI':
                return self.chameleon_port.start_capturing_audio()
            raise NotImplementedError(
                    'Audio recording from %s is not supported' % port)
        raise NotImplementedError('Audio recording on %s using %s is not '
                                  'supported' % (host, port))

    def audio_stop_recording(self, host, port):
        """Stops recording audio on a host using a port.

        @param host: The host to stop recording. E.g. 'Chameleon' or 'DUT'.
                     Currently only 'Chameleon' is supported.
        @param port: The port to record audio. Currently only 'HDMI' is
                     supported.

        @returns: It depends on stop_capturing_audio implementation on
                  different host and port.

        @raises: NotImplementedError if host/port is not supported.
        """
        if host == 'Chameleon':
            if port != self.chameleon_port.get_connector_type():
                raise ValueError(
                        'Port %s is not connected to Chameleon.' % port)
            # TODO(cychiang): Handle multiple chameleon ports.
            if port == 'HDMI':
                return self.chameleon_port.stop_capturing_audio()
            raise NotImplementedError(
                    'Audio recording from %s is not supported' % port)
        raise NotImplementedError('Audio recording on %s using %s is not '
                                  'supported' % (host, port))

    def audio_playback(self, host, file_name):
        """Starts playback audio on a host.

        @param host: The host to playback audio. E.g. 'Chameleon' or 'DUT'.
                     Currently only 'DUT' is supported.
        @param file_name: The path to the file on the host.

        @returns: It depends on playback implementation on
                  different host.

        """
        if host == 'DUT':
            return self.audio_facade.playback(file_name)
        raise NotImplementedError(
                'Audio recording on %s is not supported' % host)
