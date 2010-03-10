import logging, re, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class networking_DisableInterface(test.test):
    version = 1

    def run_once(self, iface_name='wlan0'):
        forced_up = False

        # use the right interface configuration utility
        self._ifconfig = 'ifconfig'
        if iface_name.startswith('hci'):
            self._ifconfig = 'hciconfig'

        # bring up the interface if its not already up
        if not self.is_iface_up(iface_name):
            utils.system('%s %s up' % (self._ifconfig, iface_name))
            if not self.is_iface_up(iface_name):
                raise error.TestFail('interface failed to come up')
            forced_up = True

        # bring interface down
        utils.system('%s %s down' % (self._ifconfig, iface_name))
        if self.is_iface_up(iface_name):
            raise error.TestFail('interface failed to go down')

        # if initial interface state was down, don't bring it back up
        if forced_up:
            return

        # bring interface back up
        utils.system('%s %s up' % (self._ifconfig, iface_name))
        if not self.is_iface_up(iface_name):
            raise error.TestFail('interface failed to come up')


    def is_iface_up(self, name):
        try:
            out = utils.system_output('%s %s' % (self._ifconfig, name))
        except error.CmdError, e:
            logging.info(e)
            raise error.TestNAError('test interface not found')

        match = re.search('UP', out, re.S)
        return match
