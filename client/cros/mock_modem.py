# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os, subprocess
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel


FLIMFLAM_TEST_DIR = '/usr/local/lib/flimflam/test/'
ACTIVATION_SERVER = os.path.join(FLIMFLAM_TEST_DIR, 'activation-server')
MOCK_MODEM = os.path.join(FLIMFLAM_TEST_DIR, 'fake-cromo')


class Modem(object):
    """Modem helper object for a mock modem.

    This object facilitates setting up a mock (software) 3G modem for
    running autotests on machines that do not have a physical modem.
    """

    def __init__(self, interface='eth1', modem='pseudo-modem0'):
        self.interface = interface
        self.modem = modem
        self.webserver = None
        self.mock_modem = None

    def _setup_mock_modem(self):
        """Rename an interface as a mock modem for 3G testing.

        Raises a JobError if self.interface is not running and
        therefore cannot be renamed as self.modem
        """

        # If the mock-modem is already up there's nothing for us to do.
        if backchannel.is_network_iface_running(self.modem):
            return

        # Ensure that we have an interface that can be renamed
        if not backchannel.is_network_iface_running(self.interface):
            raise error.TestError(
                'Interface %s is not available to be renamed to %s' %
                (self.interface, self.modem))

        backchannel.backchannel('setup %s %s' % (self.interface, self.modem))

    def _teardown_mock_modem(self):
        """Rename a mock modem when done using it.

        Raises a JobError if mock modem exists and cannot be torn down.
        """

        # If there is no mock-modem there's nothing for us to do.
        if not backchannel.is_network_iface_running(self.modem):
            return

        # Ensure that the interface does not already exist
        if backchannel.is_network_iface_running(self.interface):
            raise error.TestError(
                'Interface %s is already exists' % self.interface)

        backchannel.backchannel('teardown %s %s' % (self.interface, self.modem))

    def setup(self):
        self._setup_mock_modem()
        # start web server
        self.webserver = subprocess.Popen(ACTIVATION_SERVER,
                                          cwd=FLIMFLAM_TEST_DIR)
        self.mock_modem = subprocess.Popen(MOCK_MODEM,
                                           cwd=FLIMFLAM_TEST_DIR)

    def teardown(self):
        try:
            self._teardown_mock_modem()
        finally:
            if self.webserver:
                self.webserver.kill()
                self.webserver = None

            if self.mock_modem:
                self.mock_modem.kill()
                self.mock_modem = None
