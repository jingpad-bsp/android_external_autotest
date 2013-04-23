# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os.path
import uuid

from autotest_lib.client.common_lib import error


class PacketCapturer(object):
    """Delegate with capability to initiate packet captures on a remote host."""

    DEFAULT_COMMAND_IFCONFIG = 'ifconfig'
    DEFAULT_COMMAND_IP = 'ip'
    DEFAULT_COMMAND_IW = 'iw'
    DEFAULT_COMMAND_NETDUMP = 'tcpdump'


    @property
    def capture_running(self):
        """@return True iff we have at least one ongoing packet capture."""
        if self._ongoing_captures:
            return True

        return False


    def __init__(self, host, host_description=None, cmd_ifconfig=None,
                 cmd_ip=None, cmd_iw=None, cmd_netdump=None):
        self._cmd_netdump = cmd_netdump or self.DEFAULT_COMMAND_NETDUMP
        self._cmd_iw = cmd_iw or self.DEFAULT_COMMAND_IW
        self._cmd_ip = cmd_ip or self.DEFAULT_COMMAND_IP
        self._cmd_ifconfig = cmd_ifconfig or self.DEFAULT_COMMAND_IFCONFIG
        self._host = host
        self._ongoing_captures = {}
        self._cap_num = 0
        self._if_num = 0
        self._created_managed_devices = []
        self._created_raw_devices = []
        self._host_description = host_description or 'cap_%s' % uuid.uuid4().hex


    def __enter__(self):
        return self


    def __exit__(self):
        self.stop()


    def stop(self):
        """Stop ongoing captures and destroy all created devices."""
        self.stop_capture()
        self.destroy_netdump_devices()


    def create_raw_monitor(self, phy, frequency, ht_type=None,
                           monitor_device=None):
        """Create and configure a monitor type WiFi interface on a phy.

        If a device called |monitor_device| already exists, it is first removed.

        @param phy string phy name for created monitor (e.g. phy0).
        @param frequency int frequency for created monitor to watch.
        @param ht_type string optional HT type ('HT20', 'HT40+', or 'HT40-').
        @param monitor_device string name of monitor interface to create.
        @return string monitor device name created or None on failure.

        """
        if not monitor_device:
            monitor_device = 'mon%d' % self._if_num
            self._if_num += 1

        self._host.run('%s dev %s del' % (self._cmd_iw, monitor_device),
                       ignore_status=True)
        result = self._host.run('%s phy %s interface add %s type monitor' %
                                (self._cmd_iw,
                                 phy,
                                 monitor_device),
                                ignore_status=True)
        if result.exit_status:
            logging.error('Failed creating raw monitor.')
            return None

        self.configure_raw_monitor(monitor_device, frequency, ht_type)
        self._created_raw_devices.append(monitor_device)
        return monitor_device


    def configure_raw_monitor(self, monitor_device, frequency, ht_type=None):
        """Configure a raw monitor with frequency and HT params.

        Note that this will stomp on earlier device settings.

        @param monitor_device string name of device to configure.
        @param frequency int WiFi frequency to dwell on.
        @param ht_type string optional HT type ('HT20', 'HT40+', or 'HT40-').

        """
        channel_args = str(frequency)
        if ht_type:
            ht_type = ht_type.upper()
            channel_args = '%s %s' % (channel_args, ht_type)
            if ht_type not in ('HT20', 'HT40+', 'HT40-'):
                raise error.TestError('Cannot set HT mode: %s', ht_type)

        self._host.run("%s dev %s set freq %s" % (self._cmd_iw,
                                                  monitor_device,
                                                  channel_args))
        self._host.run("%s link set %s up" % (self._cmd_ip, monitor_device))


    def deconfigure_raw_monitor(self, monitor_device):
        """Deconfigure a previously configured monitor device.

        @param monitor_device string name of previously configured device.

        """
        self.host.run("%s link set %s down" % (self._cmd_ip, monitor_device))


    def create_managed_monitor(self, existing_dev, monitor_device=None):
        """Create a monitor type WiFi interface next to a managed interface.

        If a device called |monitor_device| already exists, it is first removed.

        @param existing_device string existing interface (e.g. mlan0).
        @param monitor_device string name of monitor interface to create.
        @return string monitor device name created or None on failure.

        """
        if not monitor_device:
            monitor_device = 'mon%d' % self._if_num
            self._if_num += 1
        self._host.run('%s dev %s del' % (self._cmd_iw, monitor_device),
                       ignore_status=True)
        result = self._host.run('%s dev %s interface add %s type monitor' %
                                (self._cmd_iw,
                                 existing_dev,
                                 monitor_device),
                                ignore_status=True)
        if result.exit_status:
            logging.warning('Failed creating monitor.')
            return None

        self._host.run('%s %s up' % (self._cmd_ifconfig, monitor_device))
        self._created_managed_devices.append(monitor_device)
        return monitor_device


    def destroy_netdump_devices(self):
        """Destory all devices created by create_netdump_device."""
        for device in self._created_managed_devices:
            self._host.run("%s dev %s del" % (self._cmd_iw, device))
        self._created_managed_devices = []
        for device in self._created_raw_devices:
            self._host.run("%s link set %s down" % (self._cmd_ip, device))
            self._host.run("%s dev %s del" % (self._cmd_iw, device))
        self._created_raw_devices = []


    def start_capture(self, interface, local_save_dir,
                      remote_file=None, snaplen=None):
        """Start a packet capture on an existing interface.

        @param interface string existing interface to capture on.
        @param local_save_dir string directory on local machine to hold results.
        @param remote_file string full path on remote host to hold the capture.
        @param snaplen int maximum captured frame length.
        @return int pid of started packet capture.

        """
        remote_file = (remote_file or
                       '/tmp/%s.%d.pcap' % (self._host_description,
                                            self._cap_num))
        self._cap_num += 1
        remote_log_file = '%s.log' % remote_file
        # Redirect output because SSH refuses to return until the child file
        # descriptors are closed.
        cmd = '%s -i %s -w %s -s %d >%s 2>&1 & echo $!' % (self._cmd_netdump,
                                                           interface,
                                                           remote_file,
                                                           snaplen or 0,
                                                           remote_log_file)
        logging.debug('Starting managed packet capture')
        pid = int(self._host.run(cmd).stdout)
        self._ongoing_captures[pid] = (remote_file,
                                       remote_log_file,
                                       local_save_dir)
        return pid


    def stop_capture(self, capture_pid=None):
        """Stop an ongoing packet capture, or all ongoing packet captures.

        If |capture_pid| is given, stops that capture, otherwise stops all
        ongoing captures.

        @param capture_pid int pid of ongoing packet capture or None.

        """
        if capture_pid:
            pids_to_kill = [capture_pid]
        else:
            pids_to_kill = list(self._ongoing_captures.keys())

        for pid in pids_to_kill:
            self._host.run('kill -INT %d' % pid, ignore_status=True)
            pcap, pcap_log, save_dir = self._ongoing_captures[pid]
            for remote_file in (pcap, pcap_log):
                local_file = os.path.join(save_dir,
                                          os.path.basename(remote_file))
                self._host.get_file(remote_file, local_file)
            self._ongoing_captures.pop(pid)
