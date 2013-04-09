# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib, logging, os, socket, subprocess, sys, time, xmlrpclib
import SocketServer

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, test


class ServoTest(test.test):
    """AutoTest test class to serve as a parent class for FAFT tests.

    TODO(jrbarnette):  This class is a legacy, reflecting
    refactoring that has begun but not completed.  The long term
    plan is to move all function here into FAFT specific classes.
    http://crosbug.com/33305.
    """
    version = 2

    _REMOTE_PORT = 9990
    _REMOTE_COMMAND = '/usr/local/autotest/cros/faft_client.py'
    _REMOTE_COMMAND_SHORT = 'faft_client'
    _REMOTE_LOG_FILE = '/tmp/faft_client.log'
    _SSH_CONFIG = ('-o StrictHostKeyChecking=no '
                   '-o UserKnownHostsFile=/dev/null ')

    def initialize(self, host, _, use_pyauto=False, use_faft=False):
        """Create a Servo object and install the dependency.
        """
        # TODO(jrbarnette): Part of the incomplete refactoring:
        # assert here that there are no legacy callers passing
        # parameters for functionality that's been deprecated and
        # removed.
        assert use_faft and not use_pyauto

        self.servo = host.servo
        self.faft_client = None
        self._client = host
        self._ssh_tunnel = None
        self._remote_process = None
        self._local_port = None

        # Initializes dut, may raise AssertionError if pre-defined gpio
        # sequence to set GPIO's fail.  Autotest does not handle exception
        # throwing in initialize and will cause a test to hang.
        try:
            self.servo.initialize_dut()
        except (AssertionError, xmlrpclib.Fault) as e:
            raise error.TestFail(e)

        # Install faft_client dependency.
        self._autotest_client = autotest.Autotest(self._client)
        self._autotest_client.install()
        self._launch_client()

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

    def _launch_client(self):
        """Launch a remote XML RPC connection on client with retrials.
        """
        retry = 3
        while retry:
            try:
                self._launch_client_once()
                break
            except AssertionError:
                retry -= 1
                if retry:
                    logging.info('Retry again...')
                    time.sleep(5)
                else:
                    raise

    def _launch_client_once(self):
        """Launch a remote process on client and set up an xmlrpc connection.
        """
        if self._ssh_tunnel:
            self._ssh_tunnel.terminate()
            self._ssh_tunnel = None

        # Launch RPC server remotely.
        self._kill_remote_process()
        self._launch_ssh_tunnel()

        logging.info('Client command: %s', self._REMOTE_COMMAND)
        logging.info("Logging to %s", self._REMOTE_LOG_FILE)
        full_cmd = ['ssh -n -q %s root@%s \'%s &> %s\'' % (
                      self._SSH_CONFIG, self._client.ip,
                      self._REMOTE_COMMAND, self._REMOTE_LOG_FILE)]
        logging.info('Starting process %s', ' '.join(full_cmd))
        self._remote_process = subprocess.Popen(full_cmd, shell=True)

        # Connect to RPC object.
        logging.info('Connecting to client RPC server...')
        remote_url = 'http://localhost:%s' % self._local_port
        self.faft_client = xmlrpclib.ServerProxy(remote_url, allow_none=True)
        logging.info('Server proxy: %s', remote_url)

        # Poll for client RPC server to come online.
        timeout = 20
        succeed = False
        rpc_error = None
        while timeout > 0 and not succeed:
            time.sleep(1)
            try:
                self.faft_client.system.is_available()
                succeed = True
            except (socket.error,
                    xmlrpclib.ProtocolError,
                    httplib.BadStatusLine) as e:
                logging.info('caught: %s %s, tries left: %s',
                             repr(e), str(e), timeout)
                # The client RPC server may not come online fast enough. Retry.
                timeout -= 1
                rpc_error = e
            except:
                logging.error('Unexpected error: %s', sys.exc_info()[0])
                raise

        if not succeed:
            if isinstance(rpc_error, xmlrpclib.ProtocolError):
                logging.info("A protocol error occurred")
                logging.info("URL: %s", rpc_error.url)
                logging.info("HTTP/HTTPS headers: %s", rpc_error.headers)
                logging.info("Error code: %d", rpc_error.errcode)
                logging.info("Error message: %s", rpc_error.errmsg)
            p = subprocess.Popen([
                'ssh -n -q %s root@%s \'cat %s\'' % (self._SSH_CONFIG,
                self._client.ip, self._REMOTE_LOG_FILE)], shell=True,
                stdout=subprocess.PIPE)
            logging.info('Log of running remote %s:',
                         self._REMOTE_COMMAND_SHORT)
            logging.info(p.communicate()[0])
        assert succeed, 'Timed out connecting to client RPC server.'

    def wait_for_client(self, install_deps=False, timeout=100):
        """Wait for the client to come back online.

        New remote processes will be launched if their used flags are enabled.

        @param install_deps: If True, install Autotest dependency when ready.
        @param timeout: Time in seconds to wait for the client SSH daemon to
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
        if install_deps:
            self._autotest_client.install()
        self._launch_client()
        logging.info('Server: Relaunched remote %s.', 'faft')

    def wait_for_client_offline(self, timeout=60, orig_boot_id=''):
        """Wait for the client to come offline.

        @param timeout: Time in seconds to wait the client to come offline.
        @param orig_boot_id: A string containing the original boot id.
        """
        # Wait for the client to come offline.
        while timeout > 0 and self._ping_test(self._client.ip, timeout=1):
            time.sleep(1)
            timeout -= 1

        # As get_boot_id() requires DUT online. So we move the comparison here.
        if timeout == 0 and orig_boot_id:
            if self._client.get_boot_id() != orig_boot_id:
                logging.warn('Reboot done very quickly.')
                return

        assert timeout, 'Timed out waiting for client offline.'
        logging.info('Server: Client machine is offline.')

    def kill_remote(self):
        """Call remote cleanup and kill ssh."""
        if self._remote_process and self._remote_process.poll() is None:
            try:
                self.faft_client.cleanup()
                logging.info('Cleanup succeeded.')
            except xmlrpclib.ProtocolError, e:
                logging.info('Cleanup returned protocol error: ' + str(e))
        self._terminate_all_ssh()

    def cleanup(self):
        """Delete the Servo object, call remote cleanup, and kill ssh."""
        self.kill_remote()

    def _find_unused_port(self):
        """Returns an unused TCP port."""
        server = SocketServer.TCPServer(('localhost', 0),
                                        SocketServer.BaseRequestHandler)
        _, port = server.server_address
        return port

    def _launch_ssh_tunnel(self):
        """Establish an ssh tunnel for connecting to the remote RPC server.
        """
        if self._local_port is None:
            self._local_port = self._find_unused_port()
        if not self._ssh_tunnel or self._ssh_tunnel.poll() is not None:
            self._ssh_tunnel = subprocess.Popen([
                'ssh -N -n -q %s -L %s:localhost:%s root@%s' %
                (self._SSH_CONFIG, self._local_port, self._REMOTE_PORT,
                self._client.ip)], shell=True)
            assert self._ssh_tunnel.poll() is None, \
                'The SSH tunnel on port %d is not up.' % self._local_port

    def _kill_remote_process(self):
        """Ensure the remote process and local ssh process are terminated.
        """
        kill_cmd = 'pkill -f %s' % self._REMOTE_COMMAND_SHORT
        subprocess.call(['ssh -n -q %s root@%s \'%s\'' %
                         (self._SSH_CONFIG, self._client.ip, kill_cmd)],
                        shell=True)
        if self._remote_process and self._remote_process.poll() is None:
            self._remote_process.terminate()

    def _terminate_all_ssh(self):
        """Terminate all ssh connections associated with remote processes."""
        if self._ssh_tunnel and self._ssh_tunnel.poll() is None:
            self._ssh_tunnel.terminate()
        self._kill_remote_process()
        self._ssh_tunnel = None
