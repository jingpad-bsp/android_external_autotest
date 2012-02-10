# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import fcntl
import logging
import os
import pyudev
import random
import re
import socket
import struct
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import flimflam_test_path


class EthernetDongle(object):
    """ Used for definining the desired module expect states. """

    def __init__(self, expect_speed='100', expect_duplex='full'):
        # Expected values for parameters.
        self.expected_parameters = {
            'ifconfig_status': 0,
            'duplex': expect_duplex,
            'speed': expect_speed,
            'mac_address': None,
            'ipaddress': None,
        }

    def GetParam(self, parameter):
        return self.expected_parameters[parameter]

# Supported ethernet dongles and their expect states.
CISCO_300M = EthernetDongle(expect_speed='100',
                            expect_duplex='full')

class network_EthernetStressPlug(test.test):
    version = 1

    def initialize(self):
        """ Determines and defines the bus information and interface info. """

        def get_net_device_path(device='eth0'):
            """ Uses udev to get the path of the desired internet device. """
            net_list = pyudev.Context().list_devices(subsystem='net')
            for dev in net_list:
                if device in dev.sys_path:
                    # Currently, we only support usb devices where the
                    # device path should match something of the form
                    # /sys/devices/pci.*/0000.*/usb.*/.*.
                    net_path = re.search('(/sys/devices/pci[^/]*/0000[^/]*/'
                                         'usb[^/]*/[^/]*)', dev.sys_path)
                    if net_path:
                        return net_path.groups()[0]

            raise error.TestError('No ethernet device with name %s found.'
                                  % device)

        self.interface = 'eth0'
        self.eth_syspath = get_net_device_path(self.interface)

        # Stores the status of the most recently run iteration.
        self.test_status = {
            'ipaddress': None,
            'eth_state': None,
            'reason': None,
            'last_wait': 0
        }

        # Represents the number of seconds it can take
        # for ethernet to fully come up before we flag a warning.
        self.secs_before_warning = 5

        # Represents the current number of instances in which ethernet
        # took longer than dhcp_warning_level to come up.
        self.warning_count = 0

        # The percentage of test warnings before we fail the test.
        self.warning_threshold = .25

    def GetIPAddress(self):
        """ Obtains the ipaddress of the interface. """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            return socket.inet_ntoa(fcntl.ioctl(
                   s.fileno(), 0x8915,  # SIOCGIFADDR
                   struct.pack('256s', self.interface[:15]))[20:24])
        except:
            return None

    def GetEthernetStatus(self):
        """
        Updates self.test_status with the status of the ethernet interface.

        Returns:
            True if the ethernet device is up.  False otherwise.
        """

        def ReadEthVal(param):
            """ Reads the network parameters of the interface. """
            eth_path = os.path.join('/', 'sys', 'class', 'net', self.interface,
                                    param)
            val = None
            try:
                fp = open(eth_path)
                val = fp.readline().strip()
                fp.close()
            except:
                pass
            return val

        ethernet_status = {
            'ifconfig_status': utils.system('ifconfig %s' % self.interface,
                                            ignore_status=True),
            'duplex': ReadEthVal('duplex'),
            'speed': ReadEthVal('speed'),
            'mac_address': ReadEthVal('address'),
            'ipaddress': self.GetIPAddress()
        }

        self.test_status['ipaddress'] = ethernet_status['ipaddress']

        for param, val in ethernet_status.iteritems():
            if self.dongle.GetParam(param) is None:
                # For parameters with expected values none, we check the
                # existence of a value.
                if not bool(val):
                    self.test_status['eth_state'] = False
                    self.test_status['reason'] = '%s is not ready: %s == %s' \
                                                 % (self.interface, param, val)
                    return False
            else:
                if val != self.dongle.GetParam(param):
                    self.test_status['eth_state'] = False
                    self.test_status['reason'] = '%s is not ready. (%s)\n' \
                                                 "  Expected: '%s'\n" \
                                                 "  Received: '%s'" \
                                                 % (self.interface, param,
                                                 self.dongle.GetParam(param),
                                                 val)
                    return False

        self.test_status['eth_state'] = True
        self.test_status['reason'] = None
        return True

    def _PowerEthernet(self, power=1):
        """ Sends command to change the power state of ethernet.
        Args:
          power: 0 to unplug, 1 to plug.
        """

        fp = open(os.path.join(self.eth_syspath, 'authorized'), 'w')
        fp.write('%d' % power)
        fp.close()

    def TestPowerEthernet(self, power=1, timeout=45):
        """ Tests enabling or disabling the ethernet.
        Args:
            power: 0 to unplug, 1 to plug.
            timeout: Indicates approximately the number of seconds to timeout
                     how long we should check for the success of the ethernet
                     state change.

        Returns:
            The time in seconds required for device to transfer to the desired
            state.

        Raises:
            error.TestFail if the ethernet status is not in the desired state.
        """

        start_time = time.time()
        end_time = start_time + timeout

        status_str = ['off', 'on']
        self._PowerEthernet(power)

        while time.time() < end_time:
            status = self.GetEthernetStatus()

            # If ethernet is enabled and it has an IP, or if ethernet
            # is disabled and does not have an IP, we are in the desired state.
            # Return the number of "seconds" for this to happen.
            # (translated to an approximation of the number of seconds)
            if (power and status and \
                self.test_status['ipaddress'] is not None) or \
                (not power and not status and \
                self.test_status['ipaddress'] is None):
                return time.time()-start_time

            time.sleep(1)

        else:
            logging.debug(self.test_status['reason'])
            raise error.TestFail('ERROR: %s IP is %s despite setting power to '
                                 '%s after %.2f seconds.' %
                                 (self.interface, self.test_status['ipaddress'],
                                 status_str[power],
                                 self.test_status['last_wait']))

    def RandSleep(self, min_sleep, max_sleep):
        """ Sleeps for a random duration.

        Args:
            min_sleep: Minimum sleep parameter in miliseconds.
            max_sleep: Maximum sleep parameter in miliseconds.
        """
        duration = random.randint(min_sleep, max_sleep)/1000.0
        self.test_status['last_wait'] = duration
        time.sleep(duration)

    def GetDongle(self):
        """ Todo: Logic to determine the type of dongle we are testing with.
                  For now, just return the CISCO 300M USB.
        """
        return CISCO_300M

    def run_once(self, num_runs=1):
        try:
            self.dongle = self.GetDongle()
            #Sleep for a random duration between .5 and 2 seconds
            #for unplug and plug scenarios.
            for i in range(num_runs):
                logging.debug('Iteration: %d' % i)
                if self.TestPowerEthernet(power=0) > self.secs_before_warning:
                    self.warning_count+=1

                self.RandSleep(500, 2000)
                if self.TestPowerEthernet(power=1) > self.secs_before_warning:
                    self.warning_count+=1

                self.RandSleep(500, 2000)

                if self.warning_count > num_runs * self.warning_threshold:
                    raise error.TestFail('ERROR: %.2f%% of total runs (%d) '
                                         'took longer than %d seconds for '
                                         'ethernet to come up.' %
                                         (self.warning_threshold*100, num_runs,
                                          self.secs_before_warning))

        except Exception as e:
            self._PowerEthernet(1)
            raise e
