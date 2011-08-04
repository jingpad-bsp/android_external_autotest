# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import subprocess
import time
import xmlrpclib

from autotest_lib.client.common_lib import error
from autotest_lib.server import test, autotest
import autotest_lib.server.cros.servo


class ServoTest(test.test):
    """AutoTest test class that creates and destroys a servo object.

    Servo-based server side AutoTests can inherit from this object. If the
    use_pyauto flag is True a remote session of PyAuto will also be launched.
    """
    version = 1
    # Abstracts access to all Servo functions.
    servo = None
    # Exposes RPC access to a remote PyAuto client.
    pyauto = None
    # Autotest references to the client.
    _client = None
    _client_autotest = None
    # SSH processes for communicating with the client PyAuto RPC server.
    _ssh = None
    _remote_pyauto = None
    # Enable PyAuto functionality.
    _use_pyauto = False
    # Port to look at for the client PyAuto RPC server.
    _rpc_port = 9988


    def initialize(self, host, servo_port, xml_config='servo.xml',
                   servo_vid=None, servo_pid=None, servo_serial=None,
                   use_pyauto=False):
        """Create a Servo object and install the PyAuto dependency.

        If use_pyauto is True the PyAuto dependency is installed on the client
        and a remote PyAuto server is launched and connected.
        """
        self.servo = autotest_lib.server.cros.servo.Servo(
                servo_port, xml_config, servo_vid, servo_pid, servo_serial)

        # Initializes dut, may raise AssertionError if pre-defined gpio
        # sequence to set GPIO's fail.  Autotest does not handle exception
        # throwing in initialize and will cause a test to hang.
        try:
            self.servo.initialize_dut()
        except AssertionError as e:
            del self.servo
            raise error.TestFail(e)

        self._client = host;

        # Install PyAuto dependency.
        self._use_pyauto = use_pyauto
        if self._use_pyauto:
            self._client_autotest = autotest.Autotest(self._client)
            self._client_autotest.run_test('desktopui_ServoPyAuto')
            self.launch_pyauto()


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


    def launch_pyauto(self):
        """Launch PyAuto on the client and set up an xmlrpc connection."""
        assert self._use_pyauto, 'PyAuto dependency not installed.'
        if not self._ssh or self._ssh.poll() is not None:
            self._launch_ssh_tunnel()
        assert self._ssh and self._ssh.poll() is None, \
            'The SSH tunnel is not up.'
        # Launch client RPC server.
        self._kill_remote_pyauto()
        pyauto_cmd = \
            'python /usr/local/autotest/cros/servo_pyauto.py --no-http-server'
        logging.info('Client command: %s' % pyauto_cmd)
        self._remote_pyauto = subprocess.Popen(['ssh -n root@%s \'%s\'' %
                                                (self._client.ip, pyauto_cmd)],
                                               shell=True)
        logging.info('Connecting to client PyAuto RPC server...')
        remote = 'http://localhost:%s' % self._rpc_port
        self.pyauto = xmlrpclib.ServerProxy(remote, allow_none=True)
        logging.info('Server proxy: %s' % remote)
        # Poll for client RPC server to come online.
        timeout = 10
        succeed = False
        while timeout > 0 and not succeed:
            time.sleep(2)
            try:
                self.pyauto.IsLinux()
                succeed = True
            except:
                timeout -= 1
        assert succeed, 'Timed out connecting to client PyAuto RPC server.'


    def wait_for_client(self):
        """Wait for the client to come back online.

        A new remote PyAuto process will be launched if use_pyauto is enabled.
        """
        timeout = 10
        # Ensure old ssh connections are terminated.
        self._terminate_all_ssh()
        # Wait for the client to come up.
        while timeout > 0 and not self.ping_test(self._client.ip):
            time.sleep(5)
            timeout -= 1
        assert timeout, 'Timed out waiting for client to reboot.'
        logging.info('Server: Client machine is back up.')
        # Relaunch remote PyAuto.
        if self._use_pyauto:
            self.launch_pyauto()
            logging.info('Server: Relaunched remote PyAuto.')


    def cleanup(self):
        """Delete the Servo object, call PyAuto cleanup, and kill ssh."""
        if self.servo:
            del self.servo
        if self._remote_pyauto and self._remote_pyauto.poll() is None:
            self.pyauto.cleanup()
        self._terminate_all_ssh()


    def _launch_ssh_tunnel(self):
        """Establish an ssh tunnel for connecting to the remote RPC server."""
        if not self._ssh or self._ssh.poll() is not None:
            self._ssh = subprocess.Popen(['ssh', '-N', '-n', '-L',
                '%s:localhost:%s' % (self._rpc_port, self._rpc_port),
                'root@%s' % self._client.ip])


    def _kill_remote_pyauto(self):
        """Ensure the remote PyAuto and local ssh process are terminated."""
        kill_cmd = 'pkill -f servo_pyauto'
        subprocess.call(['ssh -n root@%s \'%s\'' %
                         (self._client.ip, kill_cmd)],
                        shell=True)
        if self._remote_pyauto and self._remote_pyauto.poll() is None:
            self._remote_pyauto.terminate()


    def _terminate_all_ssh(self):
        """Terminate all ssh connections associated with remote PyAuto."""
        if self._ssh and self._ssh.poll() is None:
            self._ssh.terminate()
        self._kill_remote_pyauto()
