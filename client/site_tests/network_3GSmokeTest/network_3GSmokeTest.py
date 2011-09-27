# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel, network

import logging, re, socket, string, time, urllib2
import dbus, dbus.mainloop.glib, gobject

from autotest_lib.client.cros import flimflam_test_path
import flimflam, routing, mm

SERVER = 'testing-chargen.appspot.com'
BASE_URL = 'http://' + SERVER + '/'


class network_3GSmokeTest(test.test):
    version = 1

    def ConnectTo3GNetwork(self, config_timeout):
        """Attempts to connect to a 3G network using FlimFlam.

        Args:
        config_timeout:  Timeout (in seconds) before giving up on connect

        Raises:
        error.TestFail if connection fails
        """
        logging.info('ConnectTo3GNetwork')
        service = self.flim.FindCellularService()

        success, status = self.flim.ConnectService(
            service=service,
            config_timeout=config_timeout)
        if not success:
            raise error.TestFail('Could not connect: %s.' % status)

        connected_states = ['portal', 'online']
        state = self.flim.WaitForServiceState(service=service,
                                              expected_states=connected_states,
                                              timeout=15,
                                              ignore_failure=True)[0]
        if not state in connected_states:
            raise error.TestFail('Still in state %s' % state)

        return state

    def FetchUrl(self, url_pattern=
                 BASE_URL + 'download?size=%d',
                 size=10,
                 label=None):
        """Fetch the URL, write a dictionary of performance data.

        Args:
          url_pattern:  URL to download with %d to be filled in with # of
              bytes to download.
          size:  Number of bytes to download.
          label:  Label to add to performance keyval keys.
        """
        logging.info('FetchUrl')

        if not label:
            raise error.TestError('FetchUrl: no label supplied.')

        url = url_pattern % size
        start_time = time.time()
        result = urllib2.urlopen(url, timeout=self.fetch_timeout)
        bytes_received = len(result.read())
        fetch_time = time.time() - start_time
        if not fetch_time:
            raise error.TestError('FetchUrl took 0 time.')

        if bytes_received != size:
            raise error.TestError('FetchUrl:  for %d bytes, got %d.' %
                                  (size, bytes_received))

        self.write_perf_keyval(
            {'seconds_%s_fetch_time' % label: fetch_time,
             'bytes_%s_bytes_received' % label: bytes_received,
             'bits_second_%s_speed' % label: 8 * bytes_received / fetch_time}
            )

    def DisconnectFrom3GNetwork(self, disconnect_timeout):
        """Attempts to disconnect to a 3G network using FlimFlam.

        Args:
          disconnect_timeout: Wait this long for disconnect to take
              effect.  Raise if we time out.
        """
        logging.info('DisconnectFrom3GNetwork')
        service = self.flim.FindCellularService()

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
        print 'Devices: %s' % ', '.join([p for m, p in devices])
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

    def CheckInterfaceForDestination(self, host, service):
        """Checks that routes for hosts go through the device for service.

        The concern here is that our network setup may have gone wrong
        and our test connections may go over some other network than
        the one we're trying to test.  So we take all the IP addresses
        for the supplied host and make sure they go through the
        network device attached to the supplied Flimflam service.

        Args:
          host:  Destination host
          service: Flimflam service object that should be used for
            connections to host
        """
        # addrinfo records: (family, type, proto, canonname, (addr, port))
        server_addresses = [record[4][0] for
                            record in socket.getaddrinfo(SERVER, 80)]

        device = self.flim.GetObjectInterface('Device',
                                              service.GetProperties()['Device'])
        expected = device.GetProperties()['Interface']
        logging.info('Device for %s: %s', service.object_path, expected)

        routes = routing.NetworkRoutes()
        for address in server_addresses:
          interface = routes.getRouteFor(address).interface
          logging.info('interface for %s: %s', address, interface)
          if interface!= expected:
            raise error.TestFail('Target server %s uses interface %s'
                                 '(%s expected).' %
                                 (address, interface, expected))

    def run_once_internal(self, connect_count, sleep_kludge):
        bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus(mainloop=bus_loop)

        # Get to a good starting state
        network.ResetAllModems(self.flim)

        # Wait for the modem to pick up a network after being reenabled. If we
        # don't wait here, GetModemInfo() (below) might fail partway through
        # with a "I have no network!" exception, and then at the end when we
        # test that the modem info matches, it won't. Oops.
        time.sleep(5)
        self.DisconnectFrom3GNetwork(disconnect_timeout=60)

        # Get information about all the modems
        modem_info = self.GetModemInfo()

        for ii in xrange(connect_count):
            state = self.ConnectTo3GNetwork(config_timeout=120)
            self.CheckInterfaceForDestination(SERVER,
                                              self.flim.FindCellularService())

            if state == 'portal':
                kwargs = dict(
                    url_pattern=('https://quickaccess.verizonwireless.com/'
                                 'images_b2c/shared/nav/'
                                 'vz_logo_quickaccess.jpg?foo=%d'),
                    size=4476)
            else:
                kwargs = dict(size=1<<16)
            self.FetchUrl(label='3G', **kwargs)
            self.DisconnectFrom3GNetwork(disconnect_timeout=60)

            # Verify that we can still get information for all the modems
            logging.info('Info: %s' % ', '.join(modem_info))
            if len(self.GetModemInfo()) != len(modem_info):
                logging.info('NewInfo: %s' % ', '.join(self.GetModemInfo()))
                raise error.TestFail('Test shutdown: '
                                     'failed to leave modem in working state.')

            if sleep_kludge:
              logging.info('Sleeping for %.1f seconds', sleep_kludge)
              time.sleep(sleep_kludge)

    def run_once(self, connect_count=5, sleep_kludge=5, fetch_timeout=120):
        self.fetch_timeout = fetch_timeout
        with backchannel.Backchannel():
            time.sleep(3)
            self.flim = flimflam.FlimFlam()
            self.device_manager = flimflam.DeviceManager(self.flim)
            try:
                self.device_manager.ShutdownAllExcept('cellular')
                self.run_once_internal(connect_count, sleep_kludge)
            finally:
                self.device_manager.RestoreDevices()
