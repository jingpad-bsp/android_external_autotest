import logging, re, utils
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

        # Allow 'all' keyword  - builds a list to test
        if iface_name == 'all':
            ifaces = utils.system_output('ls /sys/class/net/')
            for nic in ifaces.split():
                if nic != 'lo' and not nic.startswith('sit'):
                    self.test_one_nic(nic)
        else:
            self.test_one_nic(iface_name)


    def test_one_nic(self, iface_name='wlan0'):

        forced_up=False

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
