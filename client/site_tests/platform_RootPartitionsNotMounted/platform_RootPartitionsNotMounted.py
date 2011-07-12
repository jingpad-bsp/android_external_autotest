# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class platform_RootPartitionsNotMounted(test.test):
    version = 1

    _ROOTDEV_PATH = '/usr/bin/rootdev'
    _UDEVADM_PATH = '/sbin/udevadm'
    _UPDATE_ENGINE_PATH = '/usr/sbin/update_engine'

    def get_root_partitions(self, device):
        """Gets a list of root partitions of a device.

        Gets a list of root partitions of a device by iterating through the
        sysfs hierarchy /sys/block/<device>/<partition>. Root partitions
        are expected to have a filesystem label 'C-ROOT'.

        Args:
            device: The device, specified by its device file, to examine.

        Returns:
            A list of root partitions, specified by their device file,
            (e.g. /dev/sda1) of the given device.
        """
        partitions = []
        device_node = device.lstrip('/dev/')
        sysfs_path = '/sys/block/%s' % device_node
        for path in os.listdir(sysfs_path):
            subpath = '%s/%s' % (sysfs_path, path)
            partition_file = '%s/partition' % subpath
            if os.path.isfile(partition_file) \
                and self.get_filesystem_label(subpath) == 'C-ROOT':
                    partitions.append('/dev/%s' % path)
        return partitions

    def get_filesystem_label(self, sysfs_path):
        """Gets the filesystem label of a partition.

        Gets the filesystem label of a partition specified by its sysfs path
        by calling 'udevadm info'. 'udevadm' is expected to be installed at
        /sbin on the test image.

        Args:
            sysfs_path: The sysfs path of the partition.

        Returns:
            The filesystem label of the given partition or None if partition
            has no filesystem label or the label cannot be determined.
        """
        properties = utils.run('%s info -q property --path=%s'
                % (self._UDEVADM_PATH, sysfs_path)).stdout
        for property in properties.split('\n'):
            tokens = property.split('=')
            if tokens[0] == 'ID_FS_LABEL':
                return tokens[1]
        return None

    def get_mounted_devices(self, mounts_file):
        """Gets a set of mounted devices from a given mounts file.

        Gets a set of device files that are currently mounted. This method
        parses a given mounts file (e.g. /proc/<pid>/mounts) and extracts the
        entries with a source path under /dev/.

        Returns:
            A set of device file names (e.g. /dev/sda1)
        """
        mounted_devices = set()
        try:
            entries = open(mounts_file).readlines()
        except:
            entries = []
        for entry in entries:
            node = entry.split(' ')[0]
            if node.startswith('/dev/'):
                mounted_devices.add(node)
        return mounted_devices

    def get_process_executable(self, pid):
        """Gets the executable path of a given process ID.

        Args:
            pid: Target process ID.

        Returns:
            The executable path of the given process ID or None on error.
        """
        try:
            return os.readlink('/proc/%s/exe' % pid)
        except:
            return ""

    def get_process_list(self, excluded_executables=[]):
        """Gets a list of process IDs of active processes.

        Gets a list of process IDs of active processes by looking into /proc
        and filters out those processes with a executable path that is
        excluded.

        Args:
            excluded_executables: A list of executable paths to exclude.

        Returns:
            A list of process IDs of active processes.
        """
        processes = []
        for path in os.listdir('/proc'):
            if not path.isdigit(): continue
            process_exe = self.get_process_executable(path)
            if process_exe and process_exe not in excluded_executables:
                processes.append(path)
        return processes

    def get_root_device(self):
        """Gets the root device path.

        Gets the root device path using 'rootdev'. 'rootdev' is expected to
        be installed at /usr/bin on the test image.

        Returns:
           The root device path.
        """
        return utils.run('%s -s -d' % self._ROOTDEV_PATH).stdout.strip('\n')

    def run_once(self):
        if os.geteuid() != 0:
            raise error.TestNAError('This test needs to be run under root')

        for path in [self._ROOTDEV_PATH, self._UDEVADM_PATH]:
            if not os.path.isfile(path):
                raise error.TestNAError('%s not found' % path)

        root_device = self.get_root_device()
        if not root_device:
            raise error.TestNAError('Could not find the root device')
        logging.debug('Root device: %s' % root_device)

        root_partitions = self.get_root_partitions(root_device)
        if not root_partitions:
            raise error.TestNAError('Could not find any root partition')
        logging.debug('Root partitions: %s' % ', '.join(root_partitions))

        processes = self.get_process_list([self._UPDATE_ENGINE_PATH])
        if not processes:
            raise error.TestNAError('Could not find any process')
        logging.debug('Active processes: %s' % ', '.join(processes))

        for process in processes:
            process_exe = self.get_process_executable(process)
            mounts_file = '/proc/%s/mounts' % process
            mounted_devices = self.get_mounted_devices(mounts_file)
            for partition in root_partitions:
                if partition in mounted_devices:
                    raise error.TestFail(
                            'Root partition "%s" is mounted by process %s (%s)'
                            % (partition, process, process_exe))
