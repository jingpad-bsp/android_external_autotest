# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
from contextlib import contextmanager

from autotest_lib.client.cros.chameleon import chameleon
from autotest_lib.client.cros.chameleon import chameleon_port_finder
from autotest_lib.client.cros.multimedia import local_facade_factory


class _BaseChameleonMeasurer(object):
    """Base class of performing measurement using Chameleon."""

    _TIME_WAIT_FADE_OUT = 10

    def __init__(self, cros_host, outputdir=None):
        """Initializes the object."""
        raise NotImplementedError('_BaseChameleonMeasurer.__init__')


    @contextmanager
    def start_mirrored_mode_measurement(self):
        """Starts the mirrored mode to measure.

        It iterates the connection ports between DUT and Chameleon and uses
        the first port. Sets DUT into the mirrored mode. Then yields the
        connected ports.

        It is used via a with statement, like the following:

            measurer = LocalChameleonMeasurer(cros_host, args, chrome)
            with measure.start_mirrored_mode_measurement() as chameleon_port:
                # chameleon_port is automatically plugged before this line.
                do_some_test_on(chameleon_port)
                # chameleon_port is automatically unplugged after this line.

        @yields the first connected ChameleonVideoInput which is ensured plugged
                before yielding.

        @raises TestFail if no connected video port.
        """
        finder = chameleon_port_finder.ChameleonVideoInputFinder(
                self.chameleon, self.display_facade)
        with finder.use_first_port() as chameleon_port:
            logging.info('Used Chameleon port: %s',
                         chameleon_port.get_connector_type())

            logging.info('Setting to mirrored mode')
            self.display_facade.set_mirrored(True)

            # Hide the typing cursor.
            self.display_facade.hide_typing_cursor()

            # Sleep a while to wait the pop-up window faded-out.
            time.sleep(self._TIME_WAIT_FADE_OUT)

            # Get the resolution to make sure Chameleon in a good state.
            resolution = chameleon_port.get_resolution()
            logging.info('Detected the resolution: %dx%d', *resolution)

            yield chameleon_port


class LocalChameleonMeasurer(_BaseChameleonMeasurer):
    """A simple tool to measure using Chameleon for a client test.

    This class can only be used in a client test. For a server test, use the
    RemoteChameleonMeasurer in server/cros/chameleon/chameleon_measurer.py.

    """

    def __init__(self, cros_host, args, chrome, outputdir=None):
        """Initializes the object."""
        factory = local_facade_factory.LocalFacadeFactory(chrome)
        self.display_facade = factory.create_display_facade()

        self.chameleon = chameleon.create_chameleon_board(cros_host.hostname,
                                                          args)
        self.chameleon.setup_and_reset(outputdir)
