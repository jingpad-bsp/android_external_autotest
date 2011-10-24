# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import subprocess
import time
import xmlrpclib

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, site_host_attributes, test
import autotest_lib.server.cros.servo


class ServoTest(test.test):
    """AutoTest test class that creates and destroys a servo object.

    Servo-based server side AutoTests can inherit from this object.
    There are 2 remote clients supported:
        If use_pyauto flag is True, a remote PyAuto client will be launched;
        If use_faft flag is Ture, a remote FAFT client will be launched.
    """
    version = 2
    # Abstracts access to all Servo functions.
    servo = None
    # Exposes RPC access to a remote PyAuto client.
    pyauto = None
    # Exposes RPC access to a remote FAFT client.
    faft_client = None

    # Autotest references to the client.
    _autotest_client = None
    # Remote client info list.
    _remote_infos = {
        'pyauto': {
            # Used or not.
            'used': False,
            # Reference name of RPC object in this class.
            'ref_name': 'pyauto',
            # Port number of the remote RPC.
            'port': 9988,
            # Client test for installing dependency.
            'client_test': 'desktopui_ServoPyAuto',
            # The remote command to be run.
            'remote_command': 'python /usr/local/autotest/cros/servo_pyauto.py'
                              ' --no-http-server',
            # The short form of remote command, used by pkill.
            'remote_command_short': 'servo_pyauto',
            # The remote process info.
            'remote_process': None,
            # The ssh tunnel process info.
            'ssh_tunnel': None,
            # Polling RPC function name for testing the server availability.
            'polling_rpc': 'IsLinux',
        },
        'faft': {
            'used': False,
            'ref_name': 'faft_client',
            'port': 9990,
            'client_test': 'firmware_FAFTClient',
            'remote_command': 'python /usr/local/autotest/cros/faft_client.py',
            'remote_command_short': 'faft_client',
            'remote_process': None,
            'ssh_tunnel': None,
            'polling_rpc': 'is_available',
        },
    }


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=False):
        """Create a Servo object and install the dependency.

        If use_pyauto/use_faft is True the PyAuto/FAFTClient dependency is
        installed on the client and a remote PyAuto/FAFTClient server is
        launched and connected.
        """
        # Assign default arguments for servo invocation.
        args = {
            'servo_host': 'localhost', 'servo_port': 9999,
            'xml_config': 'servo.xml', 'servo_vid': None, 'servo_pid': None,
            'servo_serial': None, 'use_pyauto': False}

        # Parse arguments from AFE and override servo defaults above.
        client_attributes = site_host_attributes.HostAttributes(host.hostname)
        if hasattr(site_host_attributes, 'servo_serial'):
            args['servo_serial'] = client_attributes.servo_serial

        # Parse arguments from command line and override previous AFE or servo
        # defaults
        for arg in cmdline_args:
            match = re.search("^(\w+)=(.+)", arg)
            if match:
                args[match.group(1)] = match.group(2)

        # Initialize servotest args.
        self._client = host;
        self._remote_infos['pyauto']['used'] = use_pyauto
        self._remote_infos['faft']['used'] = use_faft

        self.servo = autotest_lib.server.cros.servo.Servo(
            args['servo_host'], args['servo_port'], args['xml_config'],
            args['servo_vid'], args['servo_pid'], args['servo_serial'])
        # Initializes dut, may raise AssertionError if pre-defined gpio
        # sequence to set GPIO's fail.  Autotest does not handle exception
        # throwing in initialize and will cause a test to hang.
        try:
            self.servo.initialize_dut()
        except (AssertionError, xmlrpclib.Fault) as e:
            del self.servo
            raise error.TestFail(e)

        # Install PyAuto/FAFTClient dependency.
        for info in self._remote_infos.itervalues():
            if info['used']:
                if not self._autotest_client:
                    self._autotest_client = autotest.Autotest(self._client)
                self._autotest_client.run_test(info['client_test'])
                self.launch_client(info)


    def assert_ping(self):
        """Ping to assert that the device is up."""
        assert self.ping_test(self._client.ip)


    def assert_pingfail(self):
        """Ping to assert that the device is down."""
        assert not self.ping_test(self._client.ip)


    def ping_test(self, hostname, timeout=5):
        """Verify whether a host responds to a ping.

        Args:
          hostname: Hostname to ping.
          timeout: Time in seconds to wait for a response.
        """
        return subprocess.call(['ping', '-c', '1', '-W',
                                str(timeout), hostname]) == 0


    def launch_client(self, info):
        """Launch a remote process on client and set up an xmlrpc connection.

        Args:
          info: A dict of remote info, see the definition of self._remote_infos.
        """
        assert info['used'], \
            'Remote %s dependency not installed.' % info['ref_name']
        if not info['ssh_tunnel'] or info['ssh_tunnel'].poll() is not None:
            self._launch_ssh_tunnel(info)
        assert info['ssh_tunnel'] and info['ssh_tunnel'].poll() is None, \
            'The SSH tunnel is not up.'

        # Launch RPC server remotely.
        self._kill_remote_process(info)
        logging.info('Client command: %s' % info['remote_command'])
        info['remote_process'] = subprocess.Popen([
            'ssh -o "StrictHostKeyChecking no" -n root@%s \'%s\'' %
            (self._client.ip, info['remote_command'])], shell=True)

        # Connect to RPC object.
        logging.info('Connecting to client RPC server...')
        remote_url = 'http://localhost:%s' % info['port']
        setattr(self, info['ref_name'],
            xmlrpclib.ServerProxy(remote_url, allow_none=True))
        logging.info('Server proxy: %s' % remote_url)

        # Poll for client RPC server to come online.
        timeout = 10
        succeed = False
        while timeout > 0 and not succeed:
            time.sleep(2)
            try:
                remote_object = getattr(self, info['ref_name'])
                polling_rpc = getattr(remote_object, info['polling_rpc'])
                polling_rpc()
                succeed = True
            except:
                timeout -= 1
        assert succeed, 'Timed out connecting to client RPC server.'


    def wait_for_client(self):
        """Wait for the client to come back online.

        New remote processes will be launched if their used flags are enabled.
        """
        timeout = 10
        # Ensure old ssh connections are terminated.
        self._terminate_all_ssh()
        # Wait for the client to come up.
        while timeout > 0 and not self.ping_test(self._client.ip):
            time.sleep(5)
            timeout -= 1
        assert timeout, 'Timed out waiting for client to reboot.'
        logging.info('Server: Client machine is up.')
        # Relaunch remote clients.
        for name, info in self._remote_infos.iteritems():
            if info['used']:
                self.launch_client(info)
                logging.info('Server: Relaunched remote %s.' % name)


    def cleanup(self):
        """Delete the Servo object, call remote cleanup, and kill ssh."""
        if self.servo:
            del self.servo
        for info in self._remote_infos.itervalues():
            if info['remote_process'] and info['remote_process'].poll() is None:
                remote_object = getattr(self, info['ref_name'])
                remote_object.cleanup()
        self._terminate_all_ssh()


    def _launch_ssh_tunnel(self, info):
        """Establish an ssh tunnel for connecting to the remote RPC server.

        Args:
          info: A dict of remote info, see the definition of self._remote_infos.
        """
        if not info['ssh_tunnel'] or info['ssh_tunnel'].poll() is not None:
            info['ssh_tunnel'] = subprocess.Popen(['ssh', '-N', '-n', '-L',
                '%s:localhost:%s' % (info['port'], info['port']),
                'root@%s' % self._client.ip])


    def _kill_remote_process(self, info):
        """Ensure the remote process and local ssh process are terminated.

        Args:
          info: A dict of remote info, see the definition of self._remote_infos.
        """
        kill_cmd = 'pkill -f %s' % info['remote_command_short']
        subprocess.call(['ssh -n -o "StrictHostKeyChecking no" root@%s \'%s\'' %
                         (self._client.ip, kill_cmd)],
                        shell=True)
        if info['remote_process'] and info['remote_process'].poll() is None:
            info['remote_process'].terminate()


    def _terminate_all_ssh(self):
        """Terminate all ssh connections associated with remote processes."""
        for info in self._remote_infos.itervalues():
            if info['ssh_tunnel'] and info['ssh_tunnel'].poll() is None:
                info['ssh_tunnel'].terminate()
            self._kill_remote_process(info)
