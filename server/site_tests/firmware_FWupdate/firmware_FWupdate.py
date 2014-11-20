# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import tempfile

from chromite.lib import remote_access
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_FWupdate(FirmwareTest):
    """RO+RW firmware update using chromeos-firmware --mode=[recovery|factory]

    Setup Steps:
    1. Check the device is in normal mode for recovery or
       Check the device is in dev mode for factory

    Test Steps:
    2. extract shellball and repack with new bios.bin and ec.bin
    3. replace DUT shellball with the newly repacked version from #2.
    4. Reboot DUT
    5. run chromeos-firmwareupdate --mode=recovery
    6. reboot

    Verification Steps:
    1. Step 5 should result into a success message
    2. Run crossystem and check fwid and ro_fwid should display the new bios
       firmware version string.
    4. Run ectool version to check ec version. The RO version and RW version
       strings should display new ec firmware strings.
    """

    version = 1

    def initialize(self, host, cmdline_args):
        dict_args = utils.args_to_dict(cmdline_args)
        super(firmware_FWupdate, self).initialize(host, cmdline_args)
        if not set(('new_ec', 'new_bios')).issubset(set(dict_args)):
          raise error.TestError('Missing new_ec and/or new_bios argument')
        self.new_ec = dict_args['new_ec']
        self.new_bios = dict_args['new_bios']
        if not os.path.isfile(self.new_ec) or not os.path.isfile(self.new_bios):
          raise error.TestError('Failed to locate ec or bios file')
        self.new_pd = ''
        if 'new_pd' in dict_args:
          self.new_pd = dict_args['new_pd']
          if not os.path.isfile(self.new_pd):
            raise error.TestError('Failed to locate pd file')
        logging.info('EC=%s BIOS=%s PD=%s',
                     self.new_ec, self.new_bios, self.new_pd)
        self.mode = 'recovery'
        if 'mode' in dict_args:
          self.mode = dict_args['mode']
          if self.mode == 'recovery':
            self.setup_dev_mode(False)  # Set device to normal mode
          elif self.mode == 'factory':
            self.setup_dev_mode(True)   # Set device to dev mode
          else:
            raise error.TestError('Unknown mode:%s' % self.mode)

    def local_run_cmd(self, command):
        """Execute command on local system.

        @param command: shell command to be executed on local system.
        @returns command output.
        """
        logging.info('Execute %s', command)
        output = utils.system_output(command)
        logging.info('Output %s', output)
        return output

    def dut_run_cmd(self, command):
        """Execute command on DUT.

        @param command: shell command to be executed on DUT.
        @returns command output.
        """
        logging.info('Execute %s', command)
        output = self.faft_client.system.run_shell_command_get_output(command)
        logging.info('Output %s', output)
        return output

    def get_pd_version(self):
        """Get pd firmware version.

        @returns pd firmware version string if available.
        """
        if self.new_pd:
            return self.dut_run_cmd('mosys -k pd info')[0].split('"')[5]
        return ''

    def get_system_setup(self):
        """Get and return DUT system params.

        @returns DUT system params needed for this test.
        """
        return {
          'pd_version': self.get_pd_version(),
          'ec_version': self.faft_client.ec.get_version(),
          'mainfw_type':
            self.faft_client.system.get_crossystem_value('mainfw_type'),
          'ro_fwid':
            self.faft_client.system.get_crossystem_value('ro_fwid'),
          'fwid':
            self.faft_client.system.get_crossystem_value('fwid'),
        }

    def repack_shellball(self, hostname):
        """Repack DUT shellball and replace on DUT.

        @param hostname: hostname of DUT.
        """
        shellball = '/usr/sbin/chromeos-firmwareupdate'
        # Copy DUT shellball to local.
        shellball_dir = tempfile.mkdtemp(prefix='update')
        logging.info('Tmpdir shellball_dir: %s', shellball_dir)

        dut_access = remote_access.RemoteDevice(hostname, username='root')
        dut_access.CopyFromDevice(shellball, shellball_dir, mode='scp')

        # Run shellball extract.
        extract_dir = tempfile.mkdtemp(prefix='extract')
        logging.info('Tmpdir extract_dir: %s', extract_dir)
        command = '%s/chromeos-firmwareupdate --sb_extract %s' % (
                   shellball_dir, extract_dir)
        self.local_run_cmd(command)

        # Replace bin files.
        if(not os.path.isfile(os.path.join(extract_dir, 'ec.bin')) or
           not os.path.isfile(os.path.join(extract_dir, 'bios.bin'))):
          raise error.TestError('Cannot locate ec.bin or bios.bin in unpack'
                                ' dir %s', extract_dir)
        command = 'cp %s %s/ec.bin' % (self.new_ec, extract_dir)
        self.local_run_cmd(command)
        command = 'cp %s %s/bios.bin' % (self.new_bios, extract_dir)
        self.local_run_cmd(command)
        if self.new_pd:
          if not os.path.isfile(os.path.join(extract_dir, 'pd.bin')):
            raise error.TestError('Cannot locate pd.bin in unpack dir %s',
                                  extract_dir)
          command = 'cp %s %s/pd.bin' % (self.new_pd, extract_dir)
          self.local_run_cmd(command)

        # Repack shellball with new bin files.
        command = '%s/chromeos-firmwareupdate --sb_repack %s' % (
                   shellball_dir, extract_dir)
        self.local_run_cmd(command)

        # Call to "shar" in chromeos-firmwareupdate might fail and the repack
        # ignore failure and exit with 0 status (http://crosbug.com/p/33719).
        # Add additional check to ensure the repack is successful.
        command = 'tail -1 %s/chromeos-firmwareupdate' % shellball_dir
        output = self.local_run_cmd(command)
        if 'exit 0' not in output:
          raise error.TestError('Failed to repack %s/chromeos-firmwareupdate' %
                                shellball_dir)

        # Save DUT shellball as .org if not already.
        command = ('if test ! -f %s.org; then cp %s %s.org; fi' % (
                    shellball, shellball, shellball))
        self.dut_run_cmd(command)

        # Copy local shellball to DUT.
        dut_access.CopyToDevice('%s/chromeos-firmwareupdate' % shellball_dir, shellball, mode='scp')

        # Cleanup.
        logging.info('Cleanup %s %s', shellball_dir, extract_dir)
        if shellball_dir and os.path.isdir(shellball_dir):
          shutil.rmtree(shellball_dir)
        if extract_dir and os.path.isdir(extract_dir):
          shutil.rmtree(extract_dir)

    def get_fw_bin_version(self):
        """Get firmwware version from binary file.

        @returns verions for bios, ec, pd
        """
        bios_version = self.local_run_cmd('strings %s|grep Google_|head -1'
                                              % self.new_bios)
        ec_version = self.local_run_cmd('strings %s|head -1' % self.new_ec)
        pd_version = ''
        if self.new_pd:
            pd_version = self.local_run_cmd('strings %s|head -1' % self.new_pd)
        return (bios_version, ec_version, pd_version)

    def make_rootfs_writable(self, hostname):
        """Make root partition writable on 'hostname'.

        @param hostname: DUT hostname.
        """
        dut = remote_access.ChromiumOSDevice(hostname, username='root')
        dut.DisableRootfsVerification()

    def run_once(self, host):
        """Run chromeos-firmwareupdate with recovery or factory mode.

        @param host: host to run on
        """
        crossystem_before = self.get_system_setup()
        (bios_version, ec_version, pd_version) = self.get_fw_bin_version()

        # Make rootfs writeable
        self.make_rootfs_writable(host.hostname)

        # Repack shellball with new ec and bios.
        self.repack_shellball(host.hostname)

        # Flash DUT with new bios/ec.
        command = '/usr/sbin/chromeos-firmwareupdate --mode=%s' % self.mode
        self.dut_run_cmd(command)
        host.reboot()

        # Extract and verify DUT state.
        crossystem_after = self.get_system_setup()
        logging.info('crossystem BEFORE: %s', crossystem_before)
        logging.info('crossystem AFTER: %s', crossystem_after)
        logging.info('Expects bios %s', bios_version)
        logging.info('Expects ec %s', ec_version)
        logging.info('Expects pd %s', pd_version)
        assert bios_version == crossystem_after['fwid']
        assert bios_version == crossystem_after['ro_fwid']
        assert ec_version == crossystem_after['ec_version']
        assert pd_version == crossystem_after['pd_version']

