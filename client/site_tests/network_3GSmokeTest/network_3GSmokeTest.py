# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import time
import urlparse

# Import 'flimflam_test_path' first in order to import flimflam' and 'mm'.
from autotest_lib.client.cros import flimflam_test_path
import flimflam
import mm

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel, network
from autotest_lib.client.cros.cellular import cell_tools

# TODO(armansito): We should really move cros/cellular/pseudomodem/mm1.py to
# cros/cellular/, as it deprecates the old mm1.py. See crosbug.com/37005
from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim


# Default timeouts in seconds
CONNECT_TIMEOUT = 120
DISCONNECT_TIMEOUT = 60

SHILL_LOG_SCOPES = 'cellular+dbus+device+dhcp+manager+modem+portal+service'

class network_3GSmokeTest(test.test):
    version = 1

    # TODO(benchan): Migrate to use ShillProxy when ShillProxy provides a
    # similar method.
    def DisconnectFrom3GNetwork(self, disconnect_timeout):
        """Attempts to disconnect from a 3G network.

        Args:
            disconnect_timeout: Timeout in seconds for disconnecting from
                the network.

        Raises:
            error.TestFail if it fails to disconnect from the network before
               timeout.

        """
        logging.info('DisconnectFrom3GNetwork')

        service = self.flim.FindCellularService()
        if not service:
            raise error.TestError('Could not find cellular service.')

        success, status = self.flim.DisconnectService(
            service=service,
            wait_timeout=disconnect_timeout)
        if not success:
            raise error.TestFail('Could not disconnect: %s.' % status)


    def GetModemInfo(self):
        """Find all modems attached and return an dictionary of information.

        This returns a bunch of information for each modem attached to
        the system.  In practice collecting all this information
        sometimes fails if a modem is left in an odd state, so we
        collect as many things as we can to ensure that the modem is
        responding correctly.

        Returns: dictionary of information for each modem path.
        """
        results = {}

        devices = mm.EnumerateDevices()
        print 'Devices: %s' % ', '.join([p for _, p in devices])
        for manager, path in devices:
            modem = manager.Modem(path)
            props = manager.Properties(path)
            info = {}

            try:
                info = dict(info=modem.GetInfo())
                modem_type = props['Type']
                if modem_type == mm.ModemManager.CDMA_MODEM:
                    cdma_modem = manager.CdmaModem(path)

                    info['esn'] = cdma_modem.GetEsn()
                    info['rs'] = cdma_modem.GetRegistrationState()
                    info['ss'] = cdma_modem.GetServingSystem()
                    info['quality'] = cdma_modem.GetSignalQuality()

                elif modem_type == mm.ModemManager.GSM_MODEM:
                    gsm_card = manager.GsmCard(path)
                    info['imsi'] = gsm_card.GetImsi()

                    gsm_network = manager.GsmNetwork(path)
                    info['ri'] = gsm_network.GetRegistrationInfo()
                else:
                    print 'Unknown modem type %s' % modem_type
                    continue

            except dbus.exceptions.DBusException, e:
                logging.info('Info: %s.', info)
                logging.error('MODEM_DBUS_FAILURE: %s: %s.', path, e)
                continue

            results[path] = info
        return results


    def run_once_internal(self):
        # Get to a good starting state
        network.ResetAllModems(self.flim)

        # Wait for the modem to pick up a network after being reenabled. If we
        # don't wait here, GetModemInfo() (below) might fail partway through
        # with a "I have no network!" exception, and then at the end when we
        # test that the modem info matches, it won't. Oops.
        time.sleep(5)
        self.DisconnectFrom3GNetwork(disconnect_timeout=DISCONNECT_TIMEOUT)

        # Get information about all the modems
        old_modem_info = self.GetModemInfo()

        for _ in xrange(self.connect_count):
            service, state = cell_tools.ConnectToCellular(self.flim,
                                                          CONNECT_TIMEOUT)

            # TODO(armansito): The pseudomodem currently cannot connect
            # to the internet. See crosbug.com/36235
            if not self.use_pseudomodem:
                if state == 'portal':
                    url_pattern = ('https://quickaccess.verizonwireless.com/'
                                   'images_b2c/shared/nav/'
                                   'vz_logo_quickaccess.jpg?foo=%d')
                    bytes_to_fetch = 4476
                else:
                    url_pattern = network.FETCH_URL_PATTERN_FOR_TEST
                    bytes_to_fetch = 64 * 1024

                device = self.flim.GetObjectInterface(
                    'Device', service.GetProperties()['Device'])
                interface = device.GetProperties()['Interface']
                logging.info('Expected interface for %s: %s',
                             service.object_path, interface)
                network.CheckInterfaceForDestination(
                    urlparse.urlparse(url_pattern).hostname,
                    interface)

                fetch_time = network.FetchUrl(url_pattern, bytes_to_fetch,
                                              self.fetch_timeout)
                self.write_perf_keyval({
                    'seconds_3G_fetch_time': fetch_time,
                    'bytes_3G_bytes_received': bytes_to_fetch,
                    'bits_second_3G_speed': 8 * bytes_to_fetch / fetch_time
                })

            self.DisconnectFrom3GNetwork(disconnect_timeout=DISCONNECT_TIMEOUT)

            # Verify that we can still get information for all the modems
            logging.info('Old modem info: %s', ', '.join(old_modem_info))
            new_modem_info = self.GetModemInfo()
            if len(new_modem_info) != len(old_modem_info):
                logging.info('New modem info: %s', ', '.join(new_modem_info))
                raise error.TestFail('Test shutdown: '
                                     'failed to leave modem in working state.')

            if self.sleep_kludge:
                logging.info('Sleeping for %.1f seconds', self.sleep_kludge)
                time.sleep(self.sleep_kludge)


    def run_once(self, connect_count=5, use_pseudomodem=False, sleep_kludge=5,
                 fetch_timeout=120):
        self.connect_count = connect_count
        self.use_pseudomodem = use_pseudomodem
        self.sleep_kludge = sleep_kludge
        self.fetch_timeout = fetch_timeout

        with backchannel.Backchannel():
            fake_sim = sim.SIM(sim.SIM.Carrier('att'),
                               mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM)
            with pseudomodem.TestModemManagerContext(use_pseudomodem,
                                                     sim=fake_sim):
                with cell_tools.OtherDeviceShutdownContext('cellular'):
                    time.sleep(3)
                    self.flim = flimflam.FlimFlam()
                    self.flim.SetDebugTags(SHILL_LOG_SCOPES)
                    self.run_once_internal()
