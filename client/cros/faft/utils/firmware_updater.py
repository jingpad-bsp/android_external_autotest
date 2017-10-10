# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module to support automatic firmware update.

See FirmwareUpdater object below.
"""

import os
import re

from autotest_lib.client.cros.faft.utils import shell_wrapper


class FirmwareUpdater(object):
    """An object to support firmware update.

    This object will create a temporary directory in /var/tmp/faft/autest with
    two subdirectory keys/ and work/. You can modify the keys in keys/
    directory. If you want to provide a given shellball to do firmware update,
    put shellball under /var/tmp/faft/autest with name chromeos-firmwareupdate.
    """

    CBFSTOOL = 'cbfstool'
    HEXDUMP = 'hexdump -v -e \'1/1 "0x%02x\\n"\''
    SIGNER = '/usr/share/vboot/bin/make_dev_firmware.sh'

    def __init__(self, os_if):
        self.os_if = os_if
        self._temp_path = '/var/tmp/faft/autest'
        self._cbfs_work_path = os.path.join(self._temp_path, 'cbfs')
        self._keys_path = os.path.join(self._temp_path, 'keys')
        self._work_path = os.path.join(self._temp_path, 'work')
        self._bios_path = 'bios.bin'
        self._ec_path = 'ec.bin'

        # _detect_image_paths always needs to run during initialization
        # or after extract_shellball is called.
        #
        # If we are setting up the temp dir from scratch, we'll transitively
        # call _detect_image_paths since extract_shellball is called.
        # Otherwise, we need to scan the existing temp directory.
        if not self.os_if.is_dir(self._temp_path):
            self._setup_temp_dir()
        else:
            self._detect_image_paths()

    def _setup_temp_dir(self):
        """Setup temporary directory.

        Devkeys are copied to _key_path. Then, shellball (default:
        /usr/sbin/chromeos-firmwareupdate) is extracted to _work_path.
        """
        self.cleanup_temp_dir()

        self.os_if.create_dir(self._temp_path)
        self.os_if.create_dir(self._cbfs_work_path)
        self.os_if.create_dir(self._work_path)
        self.os_if.copy_dir('/usr/share/vboot/devkeys', self._keys_path)

        original_shellball = '/usr/sbin/chromeos-firmwareupdate'
        working_shellball = os.path.join(self._temp_path,
                                         'chromeos-firmwareupdate')
        self.os_if.copy_file(original_shellball, working_shellball)
        self.extract_shellball()

    def cleanup_temp_dir(self):
        """Cleanup temporary directory."""
        if self.os_if.is_dir(self._temp_path):
            self.os_if.remove_dir(self._temp_path)

    def retrieve_fwid(self):
        """Retrieve shellball's fwid.

        This method should be called after setup_firmwareupdate_temp_dir.

        Returns:
            Shellball's fwid.
        """
        self.os_if.run_shell_command('dump_fmap -x %s %s' %
            (os.path.join(self._work_path, self._bios_path), 'RW_FWID_A'))

        [fwid] = self.os_if.run_shell_command_get_output(
            "cat RW_FWID_A | tr '\\0' '\\t' | cut -f1")
        return fwid

    def resign_firmware(self, version):
        """Resign firmware with version.

        Args:
            version: new firmware version number.
        """
        ro_normal = 0
        self.os_if.run_shell_command(
                '/usr/share/vboot/bin/resign_firmwarefd.sh '
                '%s %s %s %s %s %s %s %d %d' % (
                    os.path.join(self._work_path, self._bios_path),
                    os.path.join(self._temp_path, 'output.bin'),
                    os.path.join(self._keys_path, 'firmware_data_key.vbprivk'),
                    os.path.join(self._keys_path, 'firmware.keyblock'),
                    os.path.join(self._keys_path,
                                 'dev_firmware_data_key.vbprivk'),
                    os.path.join(self._keys_path, 'dev_firmware.keyblock'),
                    os.path.join(self._keys_path, 'kernel_subkey.vbpubk'),
                    version,
                    ro_normal))
        self.os_if.copy_file('%s' % os.path.join(self._temp_path, 'output.bin'),
                             '%s' % os.path.join(
                                 self._work_path, self._bios_path))

    def _detect_image_paths(self):
        """Scans shellball to find correct bios and ec image paths."""
        model_result = self.os_if.run_shell_command_get_output(
            'mosys platform model')
        if model_result:
            model = model_result[0]
            search_path = os.path.join(
                self._work_path, 'models', model, 'setvars.sh')
            grep_result = self.os_if.run_shell_command_get_output(
                'grep IMAGE_MAIN= %s' % search_path)
            if grep_result:
                match = re.match('IMAGE_MAIN=(.*)', grep_result[0])
                if match:
                    self._bios_path = match.group(1).replace('"', '')
            grep_result = self.os_if.run_shell_command_get_output(
                'grep IMAGE_EC= %s' % search_path)
            if grep_result:
                match = re.match('IMAGE_EC=(.*)', grep_result[0])
                if match:
                  self._ec_path = match.group(1).replace('"', '')

    def extract_shellball(self, append=None):
        """Extract the working shellball.

        Args:
            append: decide which shellball to use with format
                chromeos-firmwareupdate-[append]. Use 'chromeos-firmwareupdate'
                if append is None.
        """
        working_shellball = os.path.join(self._temp_path,
                                         'chromeos-firmwareupdate')
        if append:
            working_shellball = working_shellball + '-%s' % append

        self.os_if.run_shell_command('sh %s --sb_extract %s' % (
                working_shellball, self._work_path))

        self._detect_image_paths()

    def repack_shellball(self, append=None):
        """Repack shellball with new fwid.

        New fwid follows the rule: [orignal_fwid]-[append].

        Args:
            append: save the new shellball with a suffix, for example,
                chromeos-firmwareupdate-[append]. Use 'chromeos-firmwareupdate'
                if append is None.
        """
        working_shellball = os.path.join(self._temp_path,
                                         'chromeos-firmwareupdate')
        if append:
            self.os_if.copy_file(working_shellball,
                                 working_shellball + '-%s' % append)
            working_shellball = working_shellball + '-%s' % append

        self.os_if.run_shell_command('sh %s --sb_repack %s' % (
                working_shellball, self._work_path))

        if append:
            args = ['-i']
            args.append(
                    '"s/TARGET_FWID=\\"\\(.*\\)\\"/TARGET_FWID=\\"\\1.%s\\"/g"'
                    % append)
            args.append(working_shellball)
            cmd = 'sed %s' % ' '.join(args)
            self.os_if.run_shell_command(cmd)

            args = ['-i']
            args.append('"s/TARGET_UNSTABLE=\\".*\\"/TARGET_UNSTABLE=\\"\\"/g"')
            args.append(working_shellball)
            cmd = 'sed %s' % ' '.join(args)
            self.os_if.run_shell_command(cmd)

    def run_firmwareupdate(self, mode, updater_append=None, options=[]):
        """Do firmwareupdate with updater in temp_dir.

        Args:
            updater_append: decide which shellball to use with format
                chromeos-firmwareupdate-[append]. Use'chromeos-firmwareupdate'
                if updater_append is None.
            mode: ex.'autoupdate', 'recovery', 'bootok', 'factory_install'...
            options: ex. ['--noupdate_ec', '--nocheck_rw_compatible'] or [] for
                no option.
        """
        if updater_append:
            updater = os.path.join(
                self._temp_path, 'chromeos-firmwareupdate-%s' % updater_append)
        else:
            updater = os.path.join(self._temp_path, 'chromeos-firmwareupdate')
        command = '/bin/sh %s --mode %s %s' % (updater, mode, ' '.join(options))

        if mode == 'bootok':
            # Since CL:459837, bootok is moved to chromeos-setgoodfirmware.
            new_command = '/usr/sbin/chromeos-setgoodfirmware'
            command = 'if [ -e %s ]; then %s; else %s; fi' % (
                    new_command, new_command, command)

        self.os_if.run_shell_command(command)

    def cbfs_setup_work_dir(self):
        """Sets up cbfs on DUT.

        Finds bios.bin on the DUT and sets up a temp dir to operate on
        bios.bin.  If a bios.bin was specified, it is copied to the DUT
        and used instead of the native bios.bin.

        Returns:
            The cbfs work directory path.
        """

        self.os_if.remove_dir(self._cbfs_work_path)
        self.os_if.create_dir(self._cbfs_work_path)

        self.os_if.copy_file(
            os.path.join(self._work_path, self._bios_path),
            os.path.join(self._cbfs_work_path, self._bios_path))

        return self._cbfs_work_path

    def cbfs_extract_chip(self, fw_name):
        """Extracts chip firmware blob from cbfs.

        For a given chip type, looks for the corresponding firmware
        blob and hash in the specified bios.  The firmware blob and
        hash are extracted into self._cbfs_work_path.

        The extracted blobs will be <fw_name>.bin and
        <fw_name>.hash located in cbfs_work_path.

        Args:
            fw_name:
                Chip firmware name to be extracted.

        Returns:
            Boolean success status.
        """

        bios = os.path.join(self._cbfs_work_path, self._bios_path)
        fw = fw_name
        cbfs_extract = '%s %s extract -r FW_MAIN_A -n %s%%s -f %s%%s' % (
            self.CBFSTOOL,
            bios,
            fw,
            os.path.join(self._cbfs_work_path, fw))

        cmd = cbfs_extract % ('.bin', '.bin')
        if self.os_if.run_shell_command_get_status(cmd) != 0:
            return False

        cmd = cbfs_extract % ('.hash', '.hash')
        if self.os_if.run_shell_command_get_status(cmd) != 0:
            return False

        return True

    def cbfs_get_chip_hash(self, fw_name):
        """Returns chip firmware hash blob.

        For a given chip type, returns the chip firmware hash blob.
        Before making this request, the chip blobs must have been
        extracted from cbfs using cbfs_extract_chip().
        The hash data is returned as hexadecimal string.

        Args:
            fw_name:
                Chip firmware name whose hash blob to get.

        Returns:
            Boolean success status.

        Raises:
            shell_wrapper.ShellError: Underlying remote shell
                operations failed.
        """

        hexdump_cmd = '%s %s.hash' % (
            self.HEXDUMP,
            os.path.join(self._cbfs_work_path, fw_name))
        hashblob = self.os_if.run_shell_command_get_output(hexdump_cmd)
        return hashblob

    def cbfs_replace_chip(self, fw_name):
        """Replaces chip firmware in CBFS (bios.bin).

        For a given chip type, replaces its firmware blob and hash in
        bios.bin.  All files referenced are expected to be in the
        directory set up using cbfs_setup_work_dir().

        Args:
            fw_name:
                Chip firmware name to be replaced.

        Returns:
            Boolean success status.

        Raises:
            shell_wrapper.ShellError: Underlying remote shell
                operations failed.
        """

        bios = os.path.join(self._cbfs_work_path, self._bios_path)
        rm_hash_cmd = '%s %s remove -r FW_MAIN_A,FW_MAIN_B -n %s.hash' % (
            self.CBFSTOOL, bios, fw_name)
        rm_bin_cmd = '%s %s remove -r FW_MAIN_A,FW_MAIN_B -n %s.bin' % (
            self.CBFSTOOL, bios, fw_name)
        expand_cmd = '%s %s expand -r FW_MAIN_A,FW_MAIN_B' % (
            self.CBFSTOOL, bios)
        add_hash_cmd = ('%s %s add -r FW_MAIN_A,FW_MAIN_B -t raw -c none '
                        '-f %s.hash -n %s.hash') % (
                            self.CBFSTOOL,
                            bios,
                            os.path.join(self._cbfs_work_path, fw_name),
                            fw_name)
        add_bin_cmd = ('%s %s add -r FW_MAIN_A,FW_MAIN_B -t raw -c lzma '
                       '-f %s.bin -n %s.bin') % (
                           self.CBFSTOOL,
                           bios,
                           os.path.join(self._cbfs_work_path, fw_name),
                           fw_name)

        self.os_if.run_shell_command(rm_hash_cmd)
        self.os_if.run_shell_command(rm_bin_cmd)
        try:
            self.os_if.run_shell_command(expand_cmd)
        except shell_wrapper.ShellError:
            self.os_if.log(('%s may be too old, '
                            'continuing without "expand" support') %
                           self.CBFSTOOL)

        self.os_if.run_shell_command(add_hash_cmd)
        self.os_if.run_shell_command(add_bin_cmd)
        return True

    def cbfs_sign_and_flash(self):
        """Signs CBFS (bios.bin) and flashes it."""

        bios = os.path.join(self._cbfs_work_path, self._bios_path)
        signer = ('%s '
                  '--noforce_backup '
                  '--nomod_hwid '
                  '-f %s') % (self.SIGNER, bios)
        self.os_if.run_shell_command(signer)
        return True

    def get_temp_path(self):
        """Get temp directory path."""
        return self._temp_path

    def get_keys_path(self):
        """Get keys directory path."""
        return self._keys_path

    def get_cbfs_work_path(self):
        """Get cbfs work directory path."""
        return self._cbfs_work_path

    def get_work_path(self):
        """Get work directory path."""
        return self._work_path

    def get_bios_relative_path(self):
        """Gets the relative path of the bios image in the shellball."""
        return self._bios_path

    def get_ec_relative_path(self):
        """Gets the relative path of the ec image in the shellball."""
        return self._ec_path
