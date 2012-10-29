# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
A module to support automatic firmware update.

See FirmwareUpdater object below.
"""

import os
import shutil

class FirmwareUpdater(object):
    """
    An object to support firmware update.

    This object will create a temporary directory in /var/tmp/faft/autest with
    two subdirectory keys/ and work/. You can modify the keys in keys/
    directory. If you want to provide a given shellball to do firmware update,
    put shellball under /var/tmp/faft/autest with name chromeos-firmwareupdate.
    """

    def __init__(self, chros_if):
        self._temp_path = '/var/tmp/faft/autest'
        self._keys_path = os.path.join(self._temp_path, 'keys')
        self._work_path = os.path.join(self._temp_path, 'work')

        if os.path.isdir(self._temp_path):
            self._chros_if = chros_if
        else:
            self.setup(chros_if, None)


    def setup(self, chros_if, shellball=None):
        """Setup the data attributes of this class.

        This method can be called when needed.
        """
        self._chros_if = chros_if
        self._setup_temp_dir(shellball)


    def _setup_temp_dir(self, shellball=None):
        """Setup temporary directory.

        Devkeys are copied to _key_path. Then, shellball (default:
        /usr/sbin/chromeos-firmwareupdate) is extracted to _work_path.

        Args:
            shellball: Path of shellball.
        """
        self.cleanup_temp_dir()

        os.mkdir(self._temp_path)
        os.chdir(self._temp_path)

        os.mkdir(self._work_path)
        shutil.copytree('/usr/share/vboot/devkeys/', self._keys_path)

        shellball_path = os.path.join(self._temp_path,
                                      'chromeos-firmwareupdate')

        if shellball:
            shutil.copyfile(shellball, shellball_path)
        else:
            shutil.copyfile('/usr/sbin/chromeos-firmwareupdate',
                shellball_path)
        self._chros_if.run_shell_command(
            'sh %s --sb_extract %s' % (shellball_path, self._work_path))


    def cleanup_temp_dir(self):
        """Cleanup temporary directory."""
        if os.path.isdir(self._temp_path):
            shutil.rmtree(self._temp_path)


    def retrieve_fwid(self):
        """Retrieve shellball's fwid.

        This method should be called after setup_firmwareupdate_temp_dir.

        Returns:
            Shellball's fwid.
        """
        self._chros_if.run_shell_command('dump_fmap -x %s %s' %
            (os.path.join(self._work_path, 'bios.bin'), 'RW_FWID_A'))

        [fwid] = self._chros_if.run_shell_command_get_output(
            "cat RW_FWID_A | tr '\\0' '\\t' | cut -f1")
        return fwid


    def resign_firmware(self, version):
        """Resign firmware with version.

        Args:
            version: new firmware version number.
        """
        ro_normal = 1
        self._chros_if.run_shell_command(
            '/usr/share/vboot/bin/resign_firmwarefd.sh '
            '%s %s %s %s %s %s %s %d %d' % (
                os.path.join(self._work_path, 'bios.bin'),
                os.path.join(self._temp_path, 'output.bin'),
                os.path.join(self._keys_path, 'firmware_data_key.vbprivk'),
                os.path.join(self._keys_path, 'firmware.keyblock'),
                os.path.join(self._keys_path, 'dev_firmware_data_key.vbprivk'),
                os.path.join(self._keys_path, 'dev_firmware.keyblock'),
                os.path.join(self._keys_path, 'kernel_subkey.vbpubk'),
                version,
                ro_normal))
        shutil.copyfile('%s' % os.path.join(self._temp_path, 'output.bin'),
                        '%s' % os.path.join(self._work_path, 'bios.bin'))


    def repack_shellball(self, append):
        """Repack shellball with new fwid.

        New fwid follows the rule: [orignal_fwid]-[append].

        Args:
            append: use for new fwid naming.
        """
        shutil.copy('/usr/sbin/chromeos-firmwareupdate', '%s' %
            os.path.join(self._temp_path,
                         'chromeos-firmwareupdate-%s' % append))

        self._chros_if.run_shell_command('sh %s  --sb_repack %s' % (
            os.path.join(self._temp_path,
                         'chromeos-firmwareupdate-%s' % append),
            self._work_path))

        args = ['-i']
        args.append('"s/TARGET_FWID=\\"\\(.*\\)\\"/TARGET_FWID=\\"\\1.%s\\"/g"'
            % append)
        args.append('%s' % os.path.join(self._temp_path,
                                        'chromeos-firmwareupdate-%s' % append))
        cmd = 'sed %s' % ' '.join(args)
        self._chros_if.run_shell_command(cmd)

        args = ['-i']
        args.append('"s/TARGET_UNSTABLE=\\".*\\"/TARGET_UNSTABLE=\\"\\"/g"')
        args.append('%s' % os.path.join(self._temp_path,
                                        'chromeos-firmwareupdate-%s' % append))
        cmd = 'sed %s' % ' '.join(args)
        self._chros_if.run_shell_command(cmd)


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

        self._chros_if.run_shell_command(
            '/bin/sh %s --mode %s %s' % (updater, mode, ' '.join(options)))


    def get_temp_path(self):
        """Get temp directory path."""
        return self._temp_path


    def get_keys_path(self):
        """Get keys directory path."""
        return self._keys_path


    def get_work_path(self):
        """Get work directory path."""
        return self._work_path
