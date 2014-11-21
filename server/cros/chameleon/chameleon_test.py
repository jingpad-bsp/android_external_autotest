# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import chameleon_port_finder
from autotest_lib.client.cros.chameleon import chameleon_screen_test
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
        self.screen_test = chameleon_screen_test.ChameleonScreenTest(
                self.chameleon_port, self.display_facade, self.outputdir)


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
