#!/usr/bin/env python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.mainloop.glib
import gobject
import logging
import optparse
import os
import signal
import subprocess
import sys
import time

import mm1
import modemmanager
import modem_3gpp
import sim

import common
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import virtual_ethernet_pair


IFACE_NAME = 'pseudomodem0'
PEER_IFACE_NAME = IFACE_NAME + 'p'
IFACE_IP_BASE = '192.168.7'
DEFAULT_CARRIER = 'banana'
# TODO(armansito): Remove 'cromo' once it gets deprecated.
DEFAULT_MANAGERS = ['cromo', 'modemmanager']
PARENT_SLEEP_TIMEOUT = 2

class TestModemManagerContext(object):

    def __init__(self, use_pseudomodem,
                 real_managers=DEFAULT_MANAGERS,
                 sim=None,
                 modem=None):
        """
        Args:
            use_pseudomodem -- Whether or not the context should create a
                               pseudo modem manager.

            real_managers -- Array containing the names of real modem manager
                             daemons that need to be stopped before starting
                             the pseudo modem manager,
                             e.g. ['cromo', 'modemmanager']

            sim -- An instance of sim.SIM. This is required for 3GPP modems
                   as it encapsulates information about the carrier.

            modem -- An instance of a modem.Modem subclass. If none is provided
                     the default modem is an instance of modem_3gpp.Modem3GPP.

        """
        self.use_pseudomodem = use_pseudomodem
        self.real_managers = real_managers
        self.pseudo_modem = modem
        self.sim = sim
        self.pseudo_modem_manager = None

    def __enter__(self):
        if self.use_pseudomodem:
            for modem_manager in self.real_managers:
                try:
                    utils.run('/sbin/stop %s' % modem_manager)
                except error.CmdError:
                    pass
            self.pseudo_modem_manager = \
                PseudoModemManager(modem=self.pseudo_modem, sim=self.sim)
            self.pseudo_modem_manager.Start()
        return self

    def __exit__(self, *args):
        if self.use_pseudomodem:
            self.pseudo_modem_manager.Stop()
            self.pseudo_modem_manager = None
            for modem_manager in self.real_managers:
                try:
                    utils.run('/sbin/start %s' % modem_manager)
                except error.CmdError:
                    pass

    def GetPseudoModemManager(self):
        return self.pseudo_modem_manager

class VirtualEthernetInterface(object):

    def __init__(self):
        self.vif = virtual_ethernet_pair.VirtualEthernetPair(
                interface_name=IFACE_NAME,
                peer_interface_name=PEER_IFACE_NAME,
                interface_ip=None,
                peer_interface_ip=IFACE_IP_BASE + '.1/24')
        self.dnsmasq = None

    def BringIfaceUp(self):
        utils.run('sudo ifconfig %s up' % IFACE_NAME)

    def BringIfaceDown(self):
        utils.run('sudo ifconfig %s down' % IFACE_NAME);

    def StartDHCPServer(self):
        lease_file = '/tmp/dnsmasq.%s.leases' % IFACE_NAME
        os.close(os.open(lease_file, os.O_CREAT | os.O_TRUNC))
        self.dnsmasq = subprocess.Popen(
                ['sudo',
                 '/usr/local/sbin/dnsmasq',
                 '--pid-file',
                 '-k',
                 '--dhcp-leasefile=' + lease_file,
                 '--dhcp-range=%s.2,%s.254' % (
                        IFACE_IP_BASE, IFACE_IP_BASE),
                 '--port=0',
                 '--interface=' + PEER_IFACE_NAME,
                 '--bind-interfaces'
                ])

    def StopDHCPServer(self):
        if self.dnsmasq:
            self.dnsmasq.terminate()

    def RestartDHCPServer(self):
        self.StopDHCPServer()
        self.StartDHCPServer()

    def Setup(self):
        self.vif.setup()
        self.BringIfaceDown()
        if not self.vif.is_healthy:
            raise Exception('Could not initialize virtual ethernet pair')
        utils.run('sudo route add -host 255.255.255.255 dev ' +
                   PEER_IFACE_NAME)

        # Make sure 'dnsmasq' can receive DHCP requests.
        utils.run('sudo iptables -I INPUT -p udp --dport 67 -j ACCEPT')
        utils.run('sudo iptables -I INPUT -p udp --dport 68 -j ACCEPT')

        self.StartDHCPServer()

    def Teardown(self):
        self.StopDHCPServer()
        try:
            utils.run('sudo route del -host 255.255.255.255 dev ' +
                       PEER_IFACE_NAME)
        except:
            pass

        # Remove iptables rules.
        try:
            utils.run('sudo iptables -D INPUT -p udp --dport 67 -j ACCEPT')
            utils.run('sudo iptables -D INPUT -p udp --dport 68 -j ACCEPT')
        except:
            pass

        self.vif.teardown()

    def Restart(self):
        self.Teardown()
        self.Setup()

virtual_ethernet_interface = VirtualEthernetInterface()

class PseudoModemManager(object):
    """
    This class is responsible for setting up the virtual ethernet interfaces,
    initializing the DBus objects and running the main loop.

    This class can be utilized either using Python's with statement, or by
    calling Start and Stop:

        with PseudoModemManager(modem, sim):
            ... do stuff ...

    or

        pmm = PseudoModemManager(modem, sim)
        pmm.Start()
        ... do stuff ...
        pmm.Stop()

    The PseudoModemManager constructor takes a variable called "detach". If a
    value of True is given, the PseudoModemManager will run the main loop in
    a child process. This is particularly useful when using PseudoModemManager
    in an autotest:

        with PseudoModemManager(modem, sim, detach=True):
            ... This will run the modem manager in the background while this
            block executes. When the code in this block finishes running, the
            PseudoModemManager will automatically kill the child process.

    If detach=False, then the pseudo modem manager will run the main process
    until the process exits. PseudoModemManager is created with detach=False
    when this file is run as an executable.

    """

    def __init__(self,
                 modem=None,
                 sim=None,
                 detach=True,
                 logfile=None):
        # TODO(armansito): The following line just doesn't work.
        logging.basicConfig(format='%(asctime)-15s %(message)s',
                            filename=logfile,
                            level=logging.DEBUG)
        if not modem:
            # Create default modem
            modem = modem_3gpp.Modem3gpp()
        self.modem = modem
        self.sim = sim
        self.detach = detach
        self.child = None
        self.started = False

    def __enter__(self):
        self.Start()
        return self

    def __exit__(self, *args):
        self.Stop()

    def Start(self):
        logging.info('Starting pseudo modem manager.')
        self.started = True

        # TODO(armansito): See crosbug.com/36235
        global virtual_ethernet_interface
        virtual_ethernet_interface.Setup()
        if self.detach:
            self.child = os.fork()
            if self.child == 0:
                self._Run()
            else:
                time.sleep(PARENT_SLEEP_TIMEOUT)
        else:
            self._Run()

    def Stop(self):
        logging.info('Stopping pseudo modem manager.')
        if not self.started:
            logging.info('Not started, cannot stop.')
            return
        if self.detach:
            if self.child != 0:
                os.kill(self.child, signal.SIGINT)
                os.waitpid(self.child, 0)
                self.child = 0
                self._Cleanup()
        else:
            self._Cleanup()
        self.started = False

    def Restart(self):
        self.Stop()
        self.Start()

    def SetModem(self, new_modem):
        self.modem = new_modem
        self.Restart()
        time.sleep(5)

    def SetSIM(self, new_sim):
        self.sim = new_sim
        self.Restart()

    def _Cleanup(self):
        global virtual_ethernet_interface
        virtual_ethernet_interface.Teardown()

    def _Run(self):
        if not self.modem:
            raise Exception('No modem object has been provided.')
        dbus_loop = dbus.mainloop.glib.DBusGMainLoop()
        bus = dbus.SystemBus(private=True, mainloop=dbus_loop)
        name = dbus.service.BusName(mm1.I_MODEM_MANAGER, bus)
        self.manager = modemmanager.ModemManager(bus)

        self.modem.SetBus(bus)
        if self.sim:
            self.modem.SetSIM(self.sim)
        self.manager.Add(self.modem)

        self.mainloop = gobject.MainLoop()

        def SignalHandler(signum, frame):
            logging.info('Signal handler called with signal %s', signum)
            self.manager.Remove(self.modem)
            self.mainloop.quit()
            if self.detach:
                os._exit(0)

        signal.signal(signal.SIGINT, SignalHandler)
        signal.signal(signal.SIGTERM, SignalHandler)

        self.mainloop.run()

    def SendTextMessage(self, sender_no, text):
        # TODO(armansito): Implement
        pass


def Start(options):
    # TODO(armansito): Use options here to figure out the correct
    # modem to create
    sim_obj = sim.SIM(sim.SIM.Carrier(), mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM)
    with PseudoModemManager(sim=sim_obj, detach=False, logfile=options.logfile):
        pass

def main():
    usage = """

      Run pseudomodem to simulate a modem using the modemmanager-next
      DBus interfaces.

      Use --help for info.

    """
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-c', '--carrier', dest='carrier_name',
                      default=DEFAULT_CARRIER,
                      metavar='<carrier name>',
                      help='<carrier name> := anything')
    parser.add_option('-l', '--logfile', dest='logfile',
                      default=None,
                      metavar='<filename>',
                      help='<filename> := filename for logging output')
    parser.add_option('-t', '--technology', dest='tech',
                      default='3GPP',
                      metavar='<technology>',
                      help='<technology> := 3GPP|CDMA|LTE')

    options = parser.parse_args()[0]

    Start(options)


if __name__ == '__main__':
    main()
