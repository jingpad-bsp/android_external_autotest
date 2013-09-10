import logging, re, utils, os
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class network_DisableInterface(test.test):
    version = 1


    def run_once(self, iface_name='wlan0'):

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
                self.test_one_nic(nic)


    def test_one_nic(self, iface_name='wlan0'):

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
        try:
            out = utils.system_output('%s %s' % (self._ifconfig, name))
        except error.CmdError, e:
            logging.info(e)
            raise error.TestNAError('"ifconfig %s" gave error %d' % (name,out) )

        match = re.search('UP', out, re.S)
        return match
