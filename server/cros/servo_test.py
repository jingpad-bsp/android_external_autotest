# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import socket
import subprocess
import time
import xmlrpclib

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, site_host_attributes, test
from autotest_lib.server.cros import servo

class ServoTest(test.test):
    """AutoTest test class that creates and destroys a servo object.

    Servo-based server side AutoTests can inherit from this object.
    There are 2 remote clients supported:
        If use_pyauto flag is True, a remote PyAuto client will be launched;
        If use_faft flag is Ture, a remote FAFT client will be launched.
    """
    version = 2

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
            # The remote command to be run.
            'remote_command': 'python /usr/local/autotest/cros/remote_pyauto.py'
                              ' --no-http-server',
            # The short form of remote command, used by pkill.
            'remote_command_short': 'remote_pyauto',
            # The remote process info.
            'remote_process': None,
            # The ssh tunnel process info.
            'ssh_tunnel': None,
            # Polling RPC function name for testing the server availability.
            'polling_rpc': 'IsLinux',
            # Additional SSH options.
            'ssh_config': '-o StrictHostKeyChecking=no ',
        },
        'faft': {
            'used': False,
            'ref_name': 'faft_client',
            'port': 9990,
            'remote_command': '/usr/local/autotest/cros/faft_client.py',
            'remote_command_short': 'faft_client',
            'remote_log_file': '/tmp/faft_client.log',
            'remote_process': None,
            'ssh_tunnel': None,
            'polling_rpc': 'system.is_available',
            'ssh_config': '-o StrictHostKeyChecking=no '
                          '-o UserKnownHostsFile=/dev/null ',
        },
    }

    def _init_servo(self, host, cmdline_args):
        """Initialize `self.servo`.

        If the host has an attached servo object, use that.
        Otherwise assume that there's a locally attached servo
        device, and start servod on localhost.

        """
        if host.servo:
            self.servo = host.servo
            self._servo_is_local = False
            return

        # Assign default arguments for servo invocation.
        args = {
            'servo_host': 'localhost', 'servo_port': 9999,
            'xml_config': [], 'servo_vid': None, 'servo_pid': None,
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
                key = match.group(1)
                val = match.group(2)
                # Support multiple xml_config by appending it to a list.
                if key == 'xml_config':
                    args[key].append(val)
                else:
                    args[key] = val

        self.servo = servo.Servo()
        self._servo_is_local = True


    def _release_servo(self):
        """Clean up `self.servo` if it is locally attached."""
        self._servo_is_local = False


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=False):
        """Create a Servo object and install the dependency.

        If use_pyauto/use_faft is True the PyAuto/FAFTClient dependency is
        installed on the client and a remote PyAuto/FAFTClient server is
        launched and connected.
        """
        # Initialize servotest args.
        self._client = host
        self._remote_infos['pyauto']['used'] = use_pyauto
        self._remote_infos['faft']['used'] = use_faft

        self._init_servo(host, cmdline_args)

        # Initializes dut, may raise AssertionError if pre-defined gpio
        # sequence to set GPIO's fail.  Autotest does not handle exception
        # throwing in initialize and will cause a test to hang.
        try:
            self.servo.initialize_dut()
        except (AssertionError, xmlrpclib.Fault) as e:
            self._release_servo()
            raise error.TestFail(e)

        # Install PyAuto/FAFTClient dependency.
        for info in self._remote_infos.itervalues():
            if info['used']:
                if not self._autotest_client:
                    self._autotest_client = autotest.Autotest(self._client)
                self._autotest_client.install()
                self.launch_client(info)


    def _ping_test(self, hostname, timeout=5):
        """Verify whether a host responds to a ping.

        Args:
          hostname: Hostname to ping.
          timeout: Time in seconds to wait for a response.
        """
        with open(os.devnull, 'w') as fnull:
            return subprocess.call(
                    ['ping', '-c', '1', '-W', str(timeout), hostname],
                    stdout=fnull, stderr=fnull) == 0


    def _sshd_test(self, hostname, timeout=5):
        """Verify whether sshd is running in host.

        Args:
          hostname: Hostname to verify.
          timeout: Time in seconds to wait for a response.
        """
        try:
            sock = socket.create_connection((hostname, 22), timeout=timeout)
            sock.close()
            return True
        except socket.timeout:
            return False
        except socket.error:
            time.sleep(timeout)
            return False


    def launch_client(self, info):
        """Launch a remote XML RPC connection on client with retrials.

        Args:
          info: A dict of remote info, see the definition of self._remote_infos.
        """
        retry = 3
        while retry:
            try:
                self._launch_client_once(info)
                break
            except AssertionError:
                retry -= 1
                if retry:
                    logging.info('Retry again...')
                    time.sleep(5)
                else:
                    raise


    def _launch_client_once(self, info):
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
        logging.info('Client command: %s', info['remote_command'])
        if 'remote_log_file' in info:
            log_file = info['remote_log_file']
        else:
            log_file = '/dev/null'
        logging.info("Logging to %s", log_file)
        info['remote_process'] = subprocess.Popen([
            'ssh -n -q %s root@%s \'%s &> %s\'' % (info['ssh_config'],
            self._client.ip, info['remote_command'], log_file)],
            shell=True)

        # Connect to RPC object.
        logging.info('Connecting to client RPC server...')
        remote_url = 'http://localhost:%s' % info['port']
        setattr(self, info['ref_name'],
            xmlrpclib.ServerProxy(remote_url, allow_none=True))
        logging.info('Server proxy: %s', remote_url)

        # Poll for client RPC server to come online.
        timeout = 20
        succeed = False
        rpc_error = None
        while timeout > 0 and not succeed:
            time.sleep(1)
            try:
                remote_object = getattr(self, info['ref_name'])
                polling_rpc = getattr(remote_object, info['polling_rpc'])
                polling_rpc()
                succeed = True
            except (socket.error, xmlrpclib.ProtocolError) as e:
                # The client RPC server may not come online fast enough. Retry.
                timeout -= 1
                rpc_error = e

        if not succeed:
            if isinstance(rpc_error, xmlrpclib.ProtocolError):
                logging.info("A protocol error occurred")
                logging.info("URL: %s", rpc_error.url)
                logging.info("HTTP/HTTPS headers: %s", rpc_error.headers)
                logging.info("Error code: %d", rpc_error.errcode)
                logging.info("Error message: %s", rpc_error.errmsg)
            if 'remote_log_file' in info:
                p = subprocess.Popen([
                    'ssh -n -q %s root@%s \'cat %s\'' % (info['ssh_config'],
                    self._client.ip, info['remote_log_file'])], shell=True,
                    stdout=subprocess.PIPE)
                logging.info('Log of running remote %s:', info['ref_name'])
                logging.info(p.communicate()[0])
        assert succeed, 'Timed out connecting to client RPC server.'


    def wait_for_client(self, install_deps=False, timeout=100):
        """Wait for the client to come back online.

        New remote processes will be launched if their used flags are enabled.

        Args:
            install_deps: If True, install the Autotest dependency when ready.
            timeout: Time in seconds to wait for the client SSH daemon to
              come up.
        """
        # Ensure old ssh connections are terminated.
        self._terminate_all_ssh()
        # Wait for the client to come up.
        while timeout > 0 and not self._sshd_test(self._client.ip, timeout=2):
            timeout -= 2
        assert (timeout > 0), 'Timed out waiting for client to reboot.'
        logging.info('Server: Client machine is up.')
        # Relaunch remote clients.
        for name, info in self._remote_infos.iteritems():
            if info['used']:
                if install_deps:
                    if not self._autotest_client:
                        self._autotest_client = autotest.Autotest(self._client)
                    self._autotest_client.install()
                self.launch_client(info)
                logging.info('Server: Relaunched remote %s.', name)


    def wait_for_client_offline(self, timeout=60):
        """Wait for the client to come offline.

        Args:
          timeout: Time in seconds to wait the client to come offline.
        """
        # Wait for the client to come offline.
        while timeout > 0 and self._ping_test(self._client.ip, timeout=1):
            time.sleep(1)
            timeout -= 1
        assert timeout, 'Timed out waiting for client offline.'
        logging.info('Server: Client machine is offline.')


    def kill_remote(self):
        """Call remote cleanup and kill ssh."""
        for info in self._remote_infos.itervalues():
            if info['remote_process'] and info['remote_process'].poll() is None:
                remote_object = getattr(self, info['ref_name'])
                try:
                    remote_object.cleanup()
                    logging.info('Cleanup succeeded.')
                except xmlrpclib.ProtocolError, e:
                    logging.info('Cleanup returned protocol error: ' + str(e))
        self._terminate_all_ssh()


    def cleanup(self):
        """Delete the Servo object, call remote cleanup, and kill ssh."""
        self._release_servo()
        self.kill_remote()


    def _launch_ssh_tunnel(self, info):
        """Establish an ssh tunnel for connecting to the remote RPC server.

        Args:
          info: A dict of remote info, see the definition of self._remote_infos.
        """
        if not info['ssh_tunnel'] or info['ssh_tunnel'].poll() is not None:
            info['ssh_tunnel'] = subprocess.Popen([
                'ssh -N -n -q %s -L %s:localhost:%s root@%s' %
                (info['ssh_config'], info['port'], info['port'],
                self._client.ip)], shell=True)


    def _kill_remote_process(self, info):
        """Ensure the remote process and local ssh process are terminated.

        Args:
          info: A dict of remote info, see the definition of self._remote_infos.
        """
        kill_cmd = 'pkill -f %s' % info['remote_command_short']
        subprocess.call(['ssh -n -q %s root@%s \'%s\'' %
                         (info['ssh_config'], self._client.ip, kill_cmd)],
                        shell=True)
        if info['remote_process'] and info['remote_process'].poll() is None:
            info['remote_process'].terminate()


    def _terminate_all_ssh(self):
        """Terminate all ssh connections associated with remote processes."""
        for info in self._remote_infos.itervalues():
            if info['ssh_tunnel'] and info['ssh_tunnel'].poll() is None:
                info['ssh_tunnel'].terminate()
            self._kill_remote_process(info)
