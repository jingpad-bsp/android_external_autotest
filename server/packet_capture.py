# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
from random import shuffle

from autotest_lib.client.common_lib import error
from autotest_lib.server import frontend
from autotest_lib.server import hosts
from autotest_lib.server.cros import host_lock_manager
from autotest_lib.server.cros import time_util

"""
PacketCapture and PacketCapture manager, together, form a mini-suite of code
to capture packets on a specified wifi frequency and high-throughput
configuration (which is either empty or equal to one of "HT20", "HT40+", or
"HT40-".  One would use these classes as follows:

    from autotest_lib.server import packet_capture

    with packet_capture.PacketCaptureManager() as capturer:
        frequency = 5785  # For example.
        try:
            capturer.allocate_packet_capture_machine()
            capturer.start_capture(frequency)

            # Do things.

        except error.TestError as e:
            raise e

        except Exception as e:
            logging.error('Problem: %s', str(e))

        finally:
            capturer.stop_capture()
            capturer.get_capture_file('foo.bar')
"""

class PacketCapture(object):
    """
    Captures packets on a specific WiFi channel for Autotests.

    This is designed to enable Autotest servers to allocate a machine to do
    WiFi packet capture.
    """

    scan_wait_seconds = 0.1

    # TODO(wdg): Add packet capture machines to an access control list.

    def __init__(self):
        self._remote_filename = '/tmp/output.pcap'
        self._iw = 'iw'
        self._ifconfig = 'ifconfig'
        self._tcpdump = 'tcpdump'
        self._monitor_iface = 'mon0'
        self._scan_iface = 'eth_test'  # shill does not manage this iface.
        self._host = None
        self._tcpdump_pid = None
        self._tcpdump_job = None
        self.manager = host_lock_manager.HostLockManager()


    def __repr__(self):
        """@returns class name and capturer name."""
        return 'class: %s, host: %s' % (self.__class__.__name__, self._host)


    def allocate_packet_capture_machine(self, hostname=None):
        """
        Allocates a machine to capture packets.  Locks it (if packet_capture
        was discovered via AFE) so nobody else can use it.

        @param hostname string optional hostname of packet_capture host

        @raises error.TestError if unable to allocate or lock a tracer.
        """
        if hostname is not None:
            self._host = hosts.SSHHost(hostname)
        else:
            afe = frontend.AFE(debug=True)
            hosts_maybe = afe.get_hosts(multiple_labels=['packet_capture'])
            if not hosts_maybe:
                raise error.TestError('No packet capture machines available')

            self._host = None
            # Shuffle order of hosts for load distribution.
            shuffle(hosts_maybe)
            for host in hosts_maybe:
                if self.manager.lock([host.hostname]):
                    logging.info('locked %s', host.hostname)
                    self._host = hosts.SSHHost(host.hostname+'.cros')
                    break
                else:
                    logging.info('Unable to lock %s', host.hostname)

        if not self._host:
            raise error.TestError('Could not allocate a packet tracer.')

        logging.info('Allocated packet tracer: %s', self._host.hostname)


    def _delete_files_and_interfaces(self):
        """Removes packet capture file; deletes interfaces."""
        if self._host is not None:
            self._host.run('rm %s' % self._remote_filename,
                           ignore_status=True)
            self._host.run('%s dev wlan0 del' % self._iw, ignore_status=True)
            self._host.run('%s dev %s del' % (self._iw, self._monitor_iface),
                           ignore_status=True)
            self._host.run('%s dev %s del' % (self._iw, self._scan_iface),
                           ignore_status=True)


    def start_capture(self, freq, ht40=None):
        """
        Configures the packet capture interface and starts capture.

        @param freq: WiFi frequency on which to capture.
        @param ht40: High-Throughput mode (if any) on which to capture.  Legal
                values are 'HT20', 'HT40+', and 'HT40-'.
        """
        # TODO(wdg): May want to enhance this by adding a BSS or SSID
        # parameter to this method (which would be redundant with the
        # frequency and ht mode) and, by scraping an 'iw scan', verifying that
        # that it's working on the frequency and ht configuration specified.

        # Delete wifi interfaces and bring up a monitor interface.
        self._delete_files_and_interfaces()

        if not self._host:
            return

        # TODO(wdg): If this first command fails, mark the machine as broken.
        self._host.run('%s phy0 interface add %s type monitor' %
                       (self._iw, self._monitor_iface))
        self._host.run('%s %s up' % (self._ifconfig, self._monitor_iface))
        self._host.run('%s phy0 interface add %s type managed' %
                       (self._iw, self._scan_iface))
        self._host.run('%s %s up' % (self._ifconfig, self._scan_iface))

        self._freq = freq
        start_cmd = '%s %s set freq %s' % (self._iw, self._monitor_iface,
                                           str(self._freq))
        if ht40:
            if ht40 in ('HT20', 'HT40+', 'HT40-'):
                start_cmd = ' '.join([start_cmd, ht40])
            else:
                logging.error('Illegal ht40 parameter: %s, ignoring', ht40)
        self._host.run(start_cmd)

        # Launch a separate process to do the tcpdump.  Redirection in the
        # command below is necessary, because 'ssh' won't terminate until
        # background child processes close stdin, stdout, and stderr.
        command = '%s -i %s -w %s' % (self._tcpdump, self._monitor_iface,
                                      self._remote_filename)
        remote_cmd = '( %s ) </dev/null >/dev/null 2>&1 & echo $!' % command
        self._host.run(remote_cmd)

        self._assert_capture_ok()


    def _assert_capture_ok(self):
        """
        Force traffic on the previously specified frequency and verify that
        tcpdump is getting something.  Raise an exception if there's a problem.

        @raises error.TestError
        """
        self._host.run('%s %s scan freq %s' % (self._iw, self._scan_iface,
                                               self._freq))
        time.sleep(PacketCapture.scan_wait_seconds)  # Give the scan a moment...
        try:
            self._host.run('ls -l %s' % self._remote_filename)
        except Exception as e:
            logging.error('No output to %s: %s', self._remote_filename, str(e))
            raise error.TestError('tcpdump is not capturing anything')


    def stop_capture(self):
        """
        Stops capturing by terminating all running tcpdump processes.
        """
        try:
            self._host.run('killall tcpdump', timeout=30)
        except Exception as e:
            # Don't really care if this didn't run -- this is cleanup.
            pass


    def get_capture_file(self, local_file):
        """
        Retrieves output.pcap.  Puts that file in chroot in:
            /tmp/run_remote_tests.XXXX/testDir/testDir.testName/<local_file>

        @param local_file: a string.
        """
        if self._host:
            self._host.get_file(self._remote_filename, local_file)


    def done_capturing(self):
        """
        Tries to put things back the way we expected them to be when we got
        here.  Also, releases the packet capture machine so others can use it.
        """
        # Unlock the host to let other people use it.
        self.manager.unlock()
        # Put the wifi interface back in its normal configuration.
        if self._host is not None:
            self._delete_files_and_interfaces()
            self._host.run('%s phy0 interface add wlan0 type managed' %
                           self._iw)
            self._host.run('%s wlan0 up' % self._ifconfig)


    def get_datetime_float(self):
        """
        @returns a float, timestamp since epoch.
        """
        return time_util.get_datetime_float(self._host)


    def force_tlsdate_restart(self):
        """
        Invokes 'tlsdate restart' command.
        """
        time_util.force_tlsdate_restart(self._host)


class PacketCaptureManager(object):
    """
    Context manager to make sure that 'PacketCapture' shuts down properly.
    """
    def __init__(self):
        self._capturer = None
        self._hosts_locked_by = None

    # TODO(milleral): This code needs to be cleaned up once the host locking
    # code is made more usable (see crosbug.com/36072).

    def __enter__(self):
        self._capturer = PacketCapture()
        self._hosts_locked_by = host_lock_manager.HostsLockedBy(
                self._capturer.manager)
        self._hosts_locked_by.__enter__()
        return self._capturer


    def __exit__(self, exit_type, exit_value, exit_traceback):
        if self._hosts_locked_by:
            self._hosts_locked_by.__exit__(exit_type, exit_value,
                                           exit_traceback)
        if self._capturer:
            self._capturer.stop_capture()
            self._capturer.done_capturing()
