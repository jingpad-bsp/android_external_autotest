# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for cellular tests."""
import dbus, logging, string, urllib2

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import flimflam_test_path
from autotest_lib.client.cros.cellular import cellular
import flimflam


class Error(Exception):
    pass


TIMEOUT=30


def ConnectToCellular(flim, verifier, timeout=TIMEOUT):
    """Attempts to connect to a cell network using FlimFlam.

    Args:
    flim:  A flimflam object
    verifier: A network-side verifier that supports AssertDataStatusIn.
        Pass None to skip verification.
    timeout:    Timeout (in seconds) before giving up on connect

    Raises:
    Error if connection fails or times out
    """
    service = flim.FindCellularService()
    if not service:
        raise Error('Could not find cell service')
    properties = service.GetProperties(utf8_strings = True)
    logging.error('Properties are: %s', properties)

    logging.info('Connecting to cell service: %s', service)
    success, status = flim.ConnectService(
        service=service,
        assoc_timeout=timeout,
        config_timeout=timeout)

    if not success:
        # TODO(rochberg):  Turn off autoconnect
        if 'Error.AlreadyConnected' not in status['reason']:
            raise Error('Could not connect: %s.' % status)

    connected_states = ['portal', 'online']
    # We have to wait up to 10 seconds for state to go to portal
    state = flim.WaitForServiceState(service=service,
                                     expected_states=connected_states,
                                     timeout=timeout,
                                     ignore_failure=True)[0]
    if not state in connected_states:
        raise Error('Still in state %s' % state)

    if verifier:
      verifier.AssertDataStatusIn([cellular.UeStatus.ACTIVE])

    return (service, state)


def DisconnectFromCellularService(bs, flim, service):
    """Attempts to disconnect from the supplied cellular service.

    Args:
        bs:  A basestation object.  Pass None to skip basestation-side checks
        flim:  A flimflam object
        service:  A cellular service object
    """

    flim.DisconnectService(service)  # Waits for flimflam state to go to idle

    if bs:
        bs.GetAirStateVerifier().AssertDataStatusIn([
            cellular.UeStatus.DEACTIVATING, cellular.UeStatus.IDLE])

def CheckHttpConnectivity(config):
    """Check that the device can fetch HTTP pages.

    Args:
        config: A test cell config structure, with
            config['http_connectivity'].   config['http_connectivity']['url']
            should point to a URL that fetches a page small enough to be
            comfortably kept in memory.

            If config['http_connectivity']['url_required_contents'] is present,
            that string must be in the fetched URL.
    """
    http_config = config['http_connectivity']
    response = urllib2.urlopen(http_config['url'], timeout=TIMEOUT).read()

    if ('url_required_contents' in http_config and
        http_config['url_required_contents'] not in response):
        logging.error('Could not find %s in \n\t%s\n',
                      http_config['url_required_contents'], response)
        raise Error('Content downloaded, but it was incorrect')


class OtherDeviceShutdownContext(object):
    """Context manager that shuts down other devices.
    Usage:
    with cell_tools.OtherDeviceShutdownContext(flim, 'cellular'):
    block

    TODO(rochberg):  Replace flimflam.DeviceManager with this
    """
    def __init__(self, device_type, flim):
        self.device_manager = flimflam.DeviceManager(flim)
        self.device_manager.ShutdownAllExcept(device_type)

    def __enter__(self):
        return self

    def __exit__(self, exception, value, traceback):
        self.device_manager.RestoreDevices()
        return False


class BlackholeContext(object):
    """Context manager which uses IP tables to black hole access to hosts

    A host in hosts can be either a hostname or an IP address.  Using a
    hostname is potentially troublesome here due to DNS inconsistencies
    and load balancing, but iptables is generally smart with hostnames,
    inserting rules for each of the N ip addresses returned by a name
    lookup.

    Usage:
        with cell_tools.BlackholeContext(hosts):
            block
    """

    def __init__(self, hosts):
        self.hosts = hosts

    def __enter__(self):
        """Preserve original list of OUTPUT rules and blacklist self.hosts"""
        rules = utils.system_output('iptables -S OUTPUT').splitlines()
        self.original_rules = set(rules)

        for host in self.hosts:
            cmd = ' '.join(['iptables',
                            '-I OUTPUT',
                            '-d %s' % host,
                            '-j REJECT'])
            utils.run(cmd)
        return self

    def __exit__(self, exception, value, traceback):
        """ Remove all rules not in the original list."""
        rules = utils.system_output('iptables -S OUTPUT').splitlines()

        for rule in rules:
            if rule in self.original_rules:
                logging.info('preserving %s' % rule)
                continue
            rule = string.replace(rule, '-A', '-D', 1)
            logging.info('removing %s' % rule)
            utils.run('iptables %s' % rule)

        return False

class AutoConnectContext(object):
    """Context manager which sets autoconnect to either true or false

       Enable or Disable autoconnect for the cellular service.
       Restore it when done.

       Usage:
           with cell_tools.DisableAutoConnectContext(device, flim, autoconnect):
               block
    """

    def __init__(self, device, flim, autoconnect):
        self.device = device
        self.flim = flim
        self.autoconnect = autoconnect
        self.autoconnect_changed = False

    def PowerOnDevice(self, device):
        """Power on a flimflam device, ignoring in progress errors."""
        logging.info('powered = %s' % device.GetProperties()['Powered'])
        if device.GetProperties()['Powered']:
            return
        try:
            device.SetProperty("Powered", True)
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name != 'org.chromium.flimflam.Error.InProgress':
                raise e

    def __enter__(self):
        """Power up device, get the service and disable autoconnect."""
        changed = False
        self.PowerOnDevice(self.device)

        # TODO(jglasgow): generalize to use services associated with device
        service = self.flim.FindCellularService(timeout=40)
        if not service:
            raise error.TestFail('No cellular service available.')

        props = service.GetProperties()
        favorite = props['Favorite']

        if not favorite:
            logging.info('Enabling Favorite by connecting to service.')
            service.Connect()
            props = service.GetProperties()
            favorite = props['Favorite']

        autoconnect = props['AutoConnect']
        logging.info('Favorite = %s, AutoConnect = %s' % (
            favorite, autoconnect))

        if autoconnect != self.autoconnect:
            logging.info('Setting AutoConnect = %s.', self.autoconnect)
            service.SetProperty('AutoConnect', dbus.Boolean(self.autoconnect))

            props = service.GetProperties()
            favorite = props['Favorite']
            autoconnect = props['AutoConnect']
            changed = True

        if not favorite:
            raise error.TestFail('Favorite=False, but we want it to be True')

        if autoconnect != self.autoconnect:
            raise error.TestFail('AutoConnect is %s, but we want it to be %s' %
                                 (autoconnect, self.autoconnect))

        self.autoconnect_changed = changed

        return self

    def __exit__(self, exception, value, traceback):
        """Restore autoconnect state if we changed it."""
        if not self.autoconnect_changed:
            return

        self.PowerOnDevice(self.device)

        # TODO(jglasgow): generalize to use services associated with
        # device, and restore state only on changed services
        service = self.flim.FindCellularService()
        if not service:
            logging.error('Cannot find cellular service.  '
                          'Autoconnect state not restored.')
            return
        service.SetProperty('AutoConnect', dbus.Boolean(not self.autoconnect))

        return False
