# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.server import hosts
from autotest_lib.server.cros.network import wifi_client
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import iw_runner
from autotest_lib.client.common_lib.cros.network import ping_runner
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes

WORK_CLIENT_CONNECTION_RETRIES = 3

class ConnectionWorker(object):
    """ ConnectionWorker is a thin layer of interfaces for worker classes """

    @property
    def name(self):
        """@return a string: representing name of the worker class"""
        raise NotImplementedError('Missing subclass implementation')


    def prepare_work_client(self, work_client_machine):
        """Prepare the SSHHost object into WiFiClient object

        @param work_client_machine: a SSHHost object to be wrapped

        """
        work_client_host = hosts.create_host(work_client_machine.hostname)
        # All packet captures in chaos lab have dual NICs. Let us use phy1 to
        # be a radio dedicated for work client
        iw = iw_runner.IwRunner(remote_host=work_client_host)
        phys = iw.list_phys()
        devs = iw.list_interfaces(desired_if_type='managed')
        if len(devs) > 0:
            logging.debug('Removing interfaces in work host machine %s', devs)
            for i in range(len(devs)):
                iw.remove_interface(devs[i].if_name)
        if len(phys) > 1:
            logging.debug('Adding interfaces in work host machine')
            iw.add_interface('phy1', 'work0', 'managed')
            logging.debug('Interfaces in work client %s', iw.list_interfaces())
        elif len(phys) == 1:
            raise error.TestError('Not enough phys available to create a'
                                  'work client interface %s.' %
                                   work_client_host.hostname)
        self.work_client = wifi_client.WiFiClient(work_client_host, './debug')


    def connect_work_client(self, assoc_params):
        """
        Connect client to the AP.

        Tries to connect the work client to AP in WORK_CLIENT_CONNECTION_RETRIES
        tries. If we fail to connect in all tries then we would return False
        otherwise returns True on successful connection to the AP.

        @param assoc_params: an AssociationParameters object.
        @return a boolean: True if work client is successfully connected to AP
                or False on failing to connect to the AP

        """
        if not self.work_client.shill.init_test_network_state():
            logging.error('Failed to set up isolated test context profile for '
                          'work client.')
            return False

        success = False
        for i in range(WORK_CLIENT_CONNECTION_RETRIES):
            logging.info('Connecting work client to AP')
            assoc_result = xmlrpc_datatypes.deserialize(
                           self.work_client.shill.connect_wifi(assoc_params))
            success = assoc_result.success
            if not success:
                logging.error('Connection attempt of work client failed, try %d'
                              ' reason: %s', (i+1), assoc_result.failure_reason)
            else:
                logging.info('Work client connected to the AP')
                self.ssid = assoc_params.ssid
                break
        return success


    def cleanup(self):
        """Teardown work_client"""
        self.work_client.shill.disconnect(self.ssid)
        self.work_client.shill.clean_profiles()


    def run(self, client):
        """Executes the connection worker

        @param client: WiFiClient object representing the DUT

        """
        raise NotImplementedError('Missing subclass implementation')


class ConnectionDuration(ConnectionWorker):
    """This test is to check the liveliness of the connection to the AP. """

    def __init__(self, duration_sec=30):
        """
        Holds WiFi connection open with periodic pings

        @param duration_sec: amount of time to hold connection in seconds

        """

        self.duration_sec = duration_sec


    @property
    def name(self):
        """@return a string: representing name of this class"""
        return 'duration'


    def run(self, client):
        """Periodically pings work client to check liveliness of the connection

        @param client: WiFiClient object representing the DUT

        """
        ping_config = ping_runner.PingConfig(
                             self.work_client._interface.ipv4_address, count=10)
        logging.info('Pinging work client ip: %s',
                     self.work_client._interface.ipv4_address)
        start_time = time.time()
        while time.time() - start_time < self.duration_sec:
            time.sleep(10)
            ping_result = client.ping(ping_config)
            logging.info('Connection liveness ping results:\n%r', ping_result)
