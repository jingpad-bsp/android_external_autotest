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
import time

import mm1
import modem_3gpp
import modemmanager
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
    """
    TestModemManagerContext is an easy way for an autotest to setup a pseudo
    modem manager environment. A typical test will look like:

    with pseudomodem.TestModemManagerContext(True):
        ...
        # Do stuff
        ...

    Which will stop the real modem manager that are executing and launch the
    pseudo modem manager in a subprocess.

    Passing False to the TestModemManagerContext constructor will simply render
    this class a no-op, not affecting any environment configuration.

    """
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
        """
        Returns the underlying PseudoModemManager object.

        @return An instance of PseudoModemManager, or None, if this object
                was initialized with use_pseudomodem=False.

        """
        return self.pseudo_modem_manager

class VirtualEthernetInterface(object):
    """
    VirtualEthernetInterface sets up a virtual ethernet pair and runs dnsmasq
    on one end of the pair. This is used to enable the pseudo modem to expose
    a network interface and be assigned a dynamic IP address.

    """
    def __init__(self):
        self.vif = virtual_ethernet_pair.VirtualEthernetPair(
                interface_name=IFACE_NAME,
                peer_interface_name=PEER_IFACE_NAME,
                interface_ip=None,
                peer_interface_ip=IFACE_IP_BASE + '.1/24')
        self.dnsmasq = None

    def BringIfaceUp(self):
        """
        Brings up the pseudomodem network interface.

        """
        utils.run('sudo ifconfig %s up' % IFACE_NAME)

    def BringIfaceDown(self):
        """
        Brings down the pseudomodem network interface.

        """
        utils.run('sudo ifconfig %s down' % IFACE_NAME);

    def StartDHCPServer(self):
        """
        Runs dnsmasq on the peer end of the virtual ethernet pair.

        """
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
        """
        Stops dnsmasq if its currently running on the peer end of the virtual
        ethernet pair.

        """
        if self.dnsmasq:
            self.dnsmasq.terminate()

    def RestartDHCPServer(self):
        """
        Restarts dnsmasq on the peer end of the virtual ethernet pair.

        """
        self.StopDHCPServer()
        self.StartDHCPServer()

    def Setup(self):
        """
        Sets up the virtual ethernet pair and starts dnsmasq.

        """
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
        """
        Stops dnsmasq and takes down the virtual ethernet pair.

        """
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
        """
        Restarts the configuration.

        """
        self.Teardown()
        self.Setup()

# This is the global VirtualEthernetInterface instance. Classes inside the
# pseudo modem manager can access the singleton via this variable.
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
        """
        Starts the pseudo modem manager based on the initialization parameters.
        Depending on the configuration, this method may or may not fork. If a
        subprocess is launched, a DBus mainloop will be initialized by the
        subprocess. This method sets up the virtual ethernet interfaces and
        initializes tha DBus objects and servers.

        """
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
        """
        Stops the pseudo modem manager. This means killing the subprocess,
        if any, stopping the DBus server, and tearing down the virtual ethernet
        pair.

        """
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
        """
        Restarts the pseudo modem manager.

        """
        self.Stop()
        self.Start()

    def SetModem(self, new_modem):
        """
        Sets the modem object that is exposed by the pseudo modem manager and
        restarts the pseudo modem manager.

        @param new_modem: An instance of modem.Modem to assign.

        """
        self.modem = new_modem
        self.Restart()
        time.sleep(5)

    def SetSIM(self, new_sim):
        """
        Sets the SIM object that is exposed by the pseudo modem manager and
        restarts the pseudo modem manager.

        @param new_sim: An instance of sim.SIM to assign.

        """
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

        def _SignalHandler(signum, frame):
            logging.info('Signal handler called with signal %s', signum)
            self.manager.Remove(self.modem)
            self.mainloop.quit()
            if self.detach:
                os._exit(0)

        signal.signal(signal.SIGINT, _SignalHandler)
        signal.signal(signal.SIGTERM, _SignalHandler)

        self.mainloop.run()

    def SendTextMessage(self, sender_no, text):
        """
        Allows sending a fake text message notification.

        @param sender_no: TODO
        @param text: TODO

        """
        #TODO(armansito): Implement
        raise NotImplementedError()


def Start(use_cdma=False):
    """
    Runs the pseudomodem in script mode. This function is called only by the
    main function.

    @param use_cdma: If True, the pseudo modem manager will be initialized with
                     an instance of modem_cdma.ModemCdma, otherwise the default
                     modem will be used, which is an instance of
                     modem_3gpp.Modem3gpp.

    """
    if use_cdma:
        # Import modem_cdma here to avoid circular imports.
        import modem_cdma
        m = modem_cdma.ModemCdma(modem_cdma.ModemCdma.CdmaNetwork())
        s = None
    else:
        m = None
        s = sim.SIM(sim.SIM.Carrier(), mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM)
    with PseudoModemManager(modem=m, sim=s, detach=False, logfile=None):
        pass

def main():
    """
    The main method, executed when this file is executed as a script.

    """
    usage = """

      Run pseudomodem to simulate a modem using the modemmanager-next
      DBus interfaces.

      Use --help for info.

    """

    # TODO(armansito): Correctly utilize the below options.
    # See crbug.com/238430.

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-f', '--family', dest='family',
                      metavar='<family>',
                      help='<family> := 3GPP|CDMA')

    (opts, args) = parser.parse_args()
    if not opts.family:
        print "A mandatory option '--family' is missing\n"
        parser.print_help()
        return

    family = opts.family
    if family not in [ '3GPP', 'CDMA' ]:
        print 'Unsupported family: ' + family
        return

    Start(family == 'CDMA')


if __name__ == '__main__':
    main()
