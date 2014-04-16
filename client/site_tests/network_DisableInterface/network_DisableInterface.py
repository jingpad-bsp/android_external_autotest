import logging, re, utils, os
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem_context
from autotest_lib.client.cros.networking import cellular_proxy

PSEUDOMODEM_CONNECT_TIMEOUT_SECONDS = 10
PSEUDOMODEM_INTERFACE = 'pseudomodem0'

class network_DisableInterface(test.test):
    """ Verify a network interface can be disabled. """
    version = 1


    def run_once(self, iface_name='wlan0'):
        """
        Entry function to the test.

        @param iface_name: Name of the interface to test.
                           You can additionally pass in 'all', or 'wifi_only'.

        """
        # use the right interface configuration utility
        self._ifconfig = 'ifconfig'
        if iface_name.startswith('hci'):
            self._ifconfig = 'hciconfig'
            utils.system('%s %s up' % (self._ifconfig, iface_name))

        # 'all' keyword  - use "/sys/class/net" to generate list of DUT
        # 'wifi_only' keyword  - use "iw list" to generate list of DUT
        # Client test suites can use 'all'. Server test suites can not.
        if iface_name == 'all':
            ifaces = os.listdir('/sys/class/net/')
        elif iface_name == 'wifi_only':
            ifaces = [ nic.strip() for nic in os.listdir('/sys/class/net/')
                if os.path.exists('/sys/class/net/' + nic + '/phy80211') ]
        else:
            ifaces = [ iface_name ]

        for nic in ifaces:
            if (nic != 'lo' and not nic.startswith('sit') and not
                nic.startswith('p2p') and not nic.startswith('uap')):
                if nic == PSEUDOMODEM_INTERFACE:
                    self.test_pseudomodem_nic()
                else:
                    self.test_one_nic(nic)


    def test_pseudomodem_nic(self):
        """ Handle pseudomodem specially, wait for service to appear. """
        with pseudomodem_context.PseudoModemManagerContext(True,
                                                           {'family': '3GPP'}):
            # We expect shill to autoconnect to the cellular service in order
            # to bring up the pseudomodem network interface, so wait for that
            # to happen before continuing.
            proxy = cellular_proxy.CellularProxy.get_proxy()
            cellular_service = proxy.wait_for_cellular_service_object()
            proxy.wait_for_property_in(
                    cellular_service,
                    cellular_proxy.CellularProxy.SERVICE_PROPERTY_STATE,
                    ('ready', 'portal', 'online'),
                    timeout_seconds=PSEUDOMODEM_CONNECT_TIMEOUT_SECONDS)

            self.test_one_nic(PSEUDOMODEM_INTERFACE)


    def test_one_nic(self, iface_name='wlan0'):
        """
        Bring down an interface, and verify that it's gone.

        @param iface_name: Name of the interface to check.

        """
        forced_up = False

        # bring up the interface if its not already up
        if not self.is_iface_up(iface_name):
            utils.system('%s %s up' % (self._ifconfig, iface_name))
            if not self.is_iface_up(iface_name):
                raise error.TestFail('%s failed to come up' % iface_name)
            forced_up = True

        # bring interface down
        utils.system('%s %s down' % (self._ifconfig, iface_name))
        if self.is_iface_up(iface_name):
            raise error.TestFail('%s failed to go down' % iface_name)

        # if initial interface state was down, don't bring it back up
        if forced_up:
            return

        # bring interface back up
        utils.system('%s %s up' % (self._ifconfig, iface_name))
        if not self.is_iface_up(iface_name):
            raise error.TestFail('%s failed to come back up' % iface_name)


    def is_iface_up(self, name):
        """
        Check if the interface |name| is up.

        @param name: name of the interface to check.
        @returns: True if the interface |name| is up, False otherwise.
        @raises: TestNAError if 'ifconfig' fails.

        """
        try:
            out = utils.system_output('%s %s' % (self._ifconfig, name))
        except error.CmdError, e:
            logging.info(e)
            raise error.TestNAError('"ifconfig %s" gave error %d' % (name,out) )

        match = re.search('UP', out, re.S)
        return match
