#!/usr/bin/python -u
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Exposes the FAFTClient interface over XMLRPC.

It launches a XMLRPC server and exposes the interface of FAFTClient object.
The FAFTClient object aggreates some useful functions of exisintg SAFT
libraries.
"""

import functools, os, shutil, sys, tempfile
from optparse import OptionParser
from SimpleXMLRPCServer import SimpleXMLRPCServer

from saft import cgpt_state, chromeos_interface, flashrom_handler
from saft import kernel_handler, saft_flashrom_util, tpm_handler


def allow_multiple_section_input(image_operator):
    @functools.wraps(image_operator)
    def wrapper(self, section):
        if type(section) in (tuple, list):
            for sec in section:
                image_operator(self, sec)
        else:
            image_operator(self, section)
    return wrapper


class LazyFlashromHandlerProxy:
    _loaded = False
    _obj = None

    def __init__(self, *args, **kargs):
        self._args = args
        self._kargs = kargs

    def _load(self):
        self._obj = flashrom_handler.FlashromHandler()
        self._obj.init(*self._args, **self._kargs)
        self._obj.new_image()
        self._loaded = True

    def __getattr__(self, name):
        if not self._loaded:
            self._load()
        return getattr(self._obj, name)

    def reload(self):
        self._loaded = False


class FAFTClient(object):
    """A class of FAFT client which aggregates some useful functions of SAFT.

    This class can be exposed via a XMLRPC server such that its functions can
    be accessed remotely.

    Attributes:
        _chromeos_interface: An object to encapsulate OS services functions.
        _bios_handler: An object to automate BIOS flashrom testing.
        _ec_handler: An object to automate EC flashrom testing.
        _ec_image: An object to automate EC image for autest.
        _kernel_handler: An object to provide kernel related actions.
        _tpm_handler: An object to control TPM device.
        _temp_path: Path of a temp directory.
        _keys_path: Path of a directory, keys/, in temp directory.
        _work_path: Path of a directory, work/, in temp directory.
    """

    def __init__(self):
        """Initialize the data attributes of this class."""
        # TODO(waihong): Move the explicit object.init() methods to the
        # objects' constructors (ChromeOSInterface, FlashromHandler,
        # KernelHandler, and TpmHandler).
        self._chromeos_interface = chromeos_interface.ChromeOSInterface(False)
        # We keep the state of FAFT test in a permanent directory over reboots.
        state_dir = '/var/tmp/faft'
        self._chromeos_interface.init(state_dir, log_file='/tmp/faft_log.txt')
        os.chdir(state_dir)

        self._bios_handler = LazyFlashromHandlerProxy(
                                saft_flashrom_util,
                                self._chromeos_interface,
                                None,
                                '/usr/share/vboot/devkeys',
                                'bios')

        self._ec_handler = None
        if not os.system("mosys ec info"):
            self._ec_handler = LazyFlashromHandlerProxy(
                                  saft_flashrom_util,
                                  self._chromeos_interface,
                                  'ec_root_key.vpubk',
                                  '/usr/share/vboot/devkeys',
                                  'ec')


        self._kernel_handler = kernel_handler.KernelHandler()
        # TODO(waihong): The dev_key_path is a new argument. We do that in
        # order not to break the old image and still be able to run.
        try:
            self._kernel_handler.init(self._chromeos_interface,
                                      dev_key_path='/usr/share/vboot/devkeys',
                                      internal_disk=True)
        except:
            # Copy the key to the current working directory.
            shutil.copy('/usr/share/vboot/devkeys/kernel_data_key.vbprivk', '.')
            self._kernel_handler.init(self._chromeos_interface,
                                      internal_disk=True)

        self._tpm_handler = tpm_handler.TpmHandler()
        self._tpm_handler.init(self._chromeos_interface)

        self._cgpt_state = cgpt_state.CgptState(
                'SHORT', self._chromeos_interface, self.get_root_dev())

        # Initialize temporary directory path
        self._temp_path = '/var/tmp/faft/autest'
        self._keys_path = os.path.join(self._temp_path, 'keys')
        self._work_path = os.path.join(self._temp_path, 'work')


    def _dispatch(self, method, params):
        """This _dispatch method handles string conversion especially.

        Since we turn off allow_dotted_names option. So any string conversion,
        like str(FAFTClient.method), i.e. FAFTClient.method.__str__, failed
        via XML RPC call.
        """
        is_str = method.endswith('.__str__')
        if is_str:
            method = method.rsplit('.', 1)[0]
        try:
            func = getattr(self, method)
        except AttributeError:
            raise Exception('method "%s" is not supported' % method)
        else:
            if is_str:
                return str(func)
            else:
                return func(*params)


    def is_available(self):
        """Function for polling the RPC server availability.

        Returns:
            Always True.
        """
        return True


    def run_shell_command(self, command):
        """Run shell command.

        Args:
            command: A shell command to be run.
        """
        self._chromeos_interface.log('Requesting run shell command')
        self._chromeos_interface.run_shell_command(command)


    def run_shell_command_get_output(self, command):
        """Run shell command and get its console output.

        Args:
            command: A shell command to be run.

        Returns:
            A list of strings stripped of the newline characters.
        """
        self._chromeos_interface.log(
                'Requesting run shell command and get its console output')
        return self._chromeos_interface.run_shell_command_get_output(command)


    def software_reboot(self):
        """Request software reboot."""
        self._chromeos_interface.log('Requesting software reboot')
        self._chromeos_interface.run_shell_command('reboot')


    def get_platform_name(self):
        """Get the platform name of the current system.

        Returns:
            A string of the platform name.
        """
        self._chromeos_interface.log('Requesting get platform name')
        # 'mosys platform name' sometimes fails. Let's get the verbose output.
        lines = self._chromeos_interface.run_shell_command_get_output(
                '(mosys -vvv platform name 2>&1) || echo Failed')
        if lines[-1].strip() == 'Failed':
            raise Exception('Failed getting platform name: ' + '\n'.join(lines))
        return lines[-1]


    def get_crossystem_value(self, key):
        """Get crossystem value of the requested key.

        Args:
            key: A crossystem key.

        Returns:
            A string of the requested crossystem value.
        """
        self._chromeos_interface.log('Requesting get crossystem value')
        return self._chromeos_interface.run_shell_command_get_output(
                'crossystem %s' % key)[0]


    def get_root_dev(self):
        """Get the name of root device without partition number.

        Returns:
            A string of the root device without partition number.
        """
        self._chromeos_interface.log('Requesting get root device')
        return self._chromeos_interface.get_root_dev()


    def get_root_part(self):
        """Get the name of root device with partition number.

        Returns:
            A string of the root device with partition number.
        """
        self._chromeos_interface.log('Requesting get root part')
        return self._chromeos_interface.get_root_part()


    def set_try_fw_b(self):
        """Set 'Try Frimware B' flag in crossystem."""
        self._chromeos_interface.log('Requesting restart with firmware B')
        self._chromeos_interface.cs.fwb_tries = 1


    def request_recovery_boot(self):
        """Request running in recovery mode on the restart."""
        self._chromeos_interface.log('Requesting restart in recovery mode')
        self._chromeos_interface.cs.request_recovery()


    def get_dev_boot_usb(self):
        """Get dev_boot_usb value which controls developer mode boot from USB.

        Returns:
          True if enable, False if disable.
        """
        self._chromeos_interface.log('Getting dev_boot_usb')
        return self._chromeos_interface.cs.dev_boot_usb == '1'


    def set_dev_boot_usb(self, value):
        """Set dev_boot_usb value which controls developer mode boot from USB.

        Args:
          value: True to enable, False to disable.
        """
        self._chromeos_interface.log('Setting dev_boot_usb to %s' % str(value))
        self._chromeos_interface.cs.dev_boot_usb = 1 if value else 0


    def get_gbb_flags(self):
        """Get the GBB flags.

        Returns:
            An integer of the GBB flags.
        """
        self._chromeos_interface.log('Getting GBB flags')
        return self._bios_handler.get_gbb_flags()


    def get_firmware_flags(self, section):
        """Get the preamble flags of a firmware section.

        Args:
            section: A firmware section, either 'a' or 'b'.

        Returns:
            An integer of the preamble flags.
        """
        self._chromeos_interface.log('Getting preamble flags of firmware %s' %
                                     section)
        return self._bios_handler.get_section_flags(section)


    def set_firmware_flags(self, section, flags):
        """Set the preamble flags of a firmware section.

        Args:
            section: A firmware section, either 'a' or 'b'.
            flags: An integer of preamble flags.
        """
        self._chromeos_interface.log(
            'Setting preamble flags of firmware %s to %s' % (section, flags))
        version = self.get_firmware_version(section)
        self._bios_handler.set_section_version(section, version, flags,
                                               write_through=True)


    def get_firmware_sha(self, section):
        """Get SHA1 hash of BIOS RW firmware section.

        Args:
            section: A firmware section, either 'a' or 'b'.
            flags: An integer of preamble flags.
        """
        return self._bios_handler.get_section_sha(section)


    def get_firmware_sig_sha(self, section):
        """Get SHA1 hash of firmware vblock in section."""
        return self._bios_handler.get_section_sig_sha(section)


    def get_EC_firmware_sha(self):
        """Get SHA1 hash of EC RW firmware section."""
        return self._ec_handler.get_section_sha('rw')


    def reload_firmware(self):
        """Reload the firmware image that may be changed."""
        self._bios_handler.reload()


    @allow_multiple_section_input
    def corrupt_EC(self, section):
        """Corrupt the requested EC section signature.

        Args:
            section: A EC section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Corrupting EC signature %s' %
                                     section)
        self._ec_handler.corrupt_firmware(section, corrupt_all=True)


    @allow_multiple_section_input
    def corrupt_EC_body(self, section):
        """Corrupt the requested EC section body.

        Args:
            section: An EC section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Corrupting EC body %s' %
                                     section)
        self._ec_handler.corrupt_firmware_body(section, corrupt_all=True)


    @allow_multiple_section_input
    def restore_EC(self, section):
        """Restore the previously corrupted EC section signature.

        Args:
            section: An EC section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Restoring EC signature %s' %
                                     section)
        self._ec_handler.restore_firmware(section, restore_all=True)


    @allow_multiple_section_input
    def restore_EC_body(self, section):
        """Restore the previously corrupted EC section body.

        Args:
            section: An EC section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Restoring EC body %s' %
                                     section)
        self._ec_handler.restore_firmware_body(section, restore_all=True)


    @allow_multiple_section_input
    def corrupt_firmware(self, section):
        """Corrupt the requested firmware section signature.

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Corrupting firmware signature %s' %
                                     section)
        self._bios_handler.corrupt_firmware(section)


    @allow_multiple_section_input
    def corrupt_firmware_body(self, section):
        """Corrupt the requested firmware section body.

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Corrupting firmware body %s' %
                                     section)
        self._bios_handler.corrupt_firmware_body(section)


    @allow_multiple_section_input
    def restore_firmware(self, section):
        """Restore the previously corrupted firmware section signature.

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Restoring firmware signature %s' %
                                     section)
        self._bios_handler.restore_firmware(section)


    @allow_multiple_section_input
    def restore_firmware_body(self, section):
        """Restore the previously corrupted firmware section body.

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Restoring firmware body %s' %
                                     section)
        self._bios_handler.restore_firmware_body(section)


    def get_firmware_version(self, section):
        """Retrieve firmware version of a section."""
        return self._bios_handler.get_section_version(section)


    def get_tpm_firmware_version(self):
        """Retrieve tpm firmware body version."""
        return self._tpm_handler.get_fw_version()


    def _modify_firmware_version(self, section, delta):
        """Modify firmware version for the requested section, by adding delta.

        The passed in delta, a positive or a negative number, is added to the
        original firmware version.
        """
        original_version = self.get_firmware_version(section)
        new_version = original_version + delta
        flags = self._bios_handler.get_section_flags(section)
        self._chromeos_interface.log(
                'Setting firmware section %s version from %d to %d' % (
                section, original_version, new_version))
        self._bios_handler.set_section_version(section, new_version, flags,
                                               write_through=True)

    @allow_multiple_section_input
    def move_firmware_backward(self, section):
        """Decrement firmware version for the requested section."""
        self._modify_firmware_version(section, -1)


    @allow_multiple_section_input
    def move_firmware_forward(self, section):
        """Increase firmware version for the requested section."""
        self._modify_firmware_version(section, 1)

    def get_firmware_datakey_version(self, section):
        """Return firmware data key version."""
        return self._bios_handler.get_section_datakey_version(section)

    def get_tpm_firmware_datakey_version(self):
        """Retrieve tpm firmware data key version."""
        return self._tpm_handler.get_fw_body_version()

    def retrieve_kernel_subkey_version(self,section):
        """Return kernel subkey version."""
        return self._bios_handler.get_section_kernel_subkey_version(section)

    @allow_multiple_section_input
    def corrupt_kernel(self, section):
        """Corrupt the requested kernel section.

        Args:
            section: A kernel section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Corrupting kernel %s' % section)
        self._kernel_handler.corrupt_kernel(section)


    @allow_multiple_section_input
    def restore_kernel(self, section):
        """Restore the requested kernel section (previously corrupted).

        Args:
            section: A kernel section, either 'a' or 'b'.
        """
        self._kernel_handler.restore_kernel(section)


    def _modify_kernel_version(self, section, delta):
        """Modify kernel version for the requested section, by adding delta.

        The passed in delta, a positive or a negative number, is added to the
        original kernel version.
        """
        original_version = self._kernel_handler.get_version(section)
        new_version = original_version + delta
        self._chromeos_interface.log(
                'Setting kernel section %s version from %d to %d' % (
                section, original_version, new_version))
        self._kernel_handler.set_version(section, new_version)


    @allow_multiple_section_input
    def move_kernel_backward(self, section):
        """Decrement kernel version for the requested section."""
        self._modify_kernel_version(section, -1)


    @allow_multiple_section_input
    def move_kernel_forward(self, section):
        """Increase kernel version for the requested section."""
        self._modify_kernel_version(section, 1)


    def retrieve_kernel_version(self, section):
        """Return kernel version."""
        return self._kernel_handler.get_version(section)


    def retrieve_kernel_datakey_version(self, section):
        """Return kernel datakey version."""
        return self._kernel_handler.get_datakey_version(section)


    def diff_kernel_a_b(self):
        """Compare kernel A with B.

        Returns:
            True: if kernel A is different with B.
            False: if kernel A is the same as B.
        """
        rootdev = self._chromeos_interface.get_root_dev()
        kernel_a = self._chromeos_interface.join_part(rootdev, '3')
        kernel_b = self._chromeos_interface.join_part(rootdev, '5')

        # The signature (some kind of hash) for the kernel body is stored in
        # the beginning. So compare the first 64KB (including header, preamble,
        # and signature) should be enough to check them identical.
        header_a = self._chromeos_interface.read_partition(kernel_a, 0x10000)
        header_b = self._chromeos_interface.read_partition(kernel_b, 0x10000)

        return header_a != header_b


    def is_removable_device_boot(self):
        """Check the current boot device is removable.

        Returns:
            True: if a removable device boots.
            False: if a non-removable device boots.
        """
        root_part = self._chromeos_interface.get_root_part()
        return self._chromeos_interface.is_removable_device(root_part)


    def setup_EC_image(self, ec_path):
        """Setup the new EC image for later update.

        Args:
            ec_path: The path of the EC image to be updated.
        """
        self._ec_image = flashrom_handler.FlashromHandler()
        self._ec_image.init(saft_flashrom_util,
                            self._chromeos_interface,
                            'ec_root_key.vpubk',
                            '/usr/share/vboot/devkeys',
                            'ec')
        self._ec_image.new_image(ec_path)


    def get_EC_image_sha(self):
        """Get SHA1 hash of RW firmware section of the EC autest image."""
        return self._ec_image.get_section_sha('rw')


    def update_EC_from_image(self, section, flags):
        """Update EC via software sync design.

        It copys the RW section from the EC image, which is loaded by calling
        setup_EC_image(), to the EC area of the specified RW section on the
        current AP firmware.

        Args:
            section: A firmware section on current BIOS, either 'a' or 'b'.
            flags: An integer of preamble flags.
        """
        blob = self._ec_image.get_section_body('rw')
        self._bios_handler.set_section_ecbin(section, blob,
                                             write_through=True)
        self.set_firmware_flags(section, flags)


    def dump_firmware(self, bios_path):
        """Dump the current BIOS firmware to a file, specified by bios_path.

        Args:
            bios_path: The path of the BIOS image to be written.
        """
        self._bios_handler.dump_whole(bios_path)


    def dump_firmware_rw(self, dir_path):
        """Dump the current BIOS firmware RW to dir_path.

        VBOOTA, VBOOTB, FVMAIN, FVMAINB need to be dumped.

        Args:
            dir_path: The path of directory which contains files to be written.
        """
        if not os.path.isdir(dir_path):
            raise Exception("%s doesn't exist" % dir_path)

        VBOOTA_blob = self._bios_handler.get_section_sig('a')
        VBOOTB_blob = self._bios_handler.get_section_sig('b')
        FVMAIN_blob = self._bios_handler.get_section_body('a')
        FVMAINB_blob = self._bios_handler.get_section_body('b')

        open(os.path.join(dir_path, 'VBOOTA'), 'w').write(VBOOTA_blob)
        open(os.path.join(dir_path, 'VBOOTB'), 'w').write(VBOOTB_blob)
        open(os.path.join(dir_path, 'FVMAIN'), 'w').write(FVMAIN_blob)
        open(os.path.join(dir_path, 'FVMAINB'), 'w').write(FVMAINB_blob)


    def write_firmware(self, bios_path):
        """Write the firmware from bios_path to the current system.

        Args:
            bios_path: The path of the source BIOS image.
        """
        self._bios_handler.new_image(bios_path)
        self._bios_handler.write_whole()


    def write_firmware_rw(self, dir_path):
        """Write the firmware RW from dir_path to the current system.

        VBOOTA, VBOOTB, FVMAIN, FVMAINB need to be written.

        Args:
            dir_path: The path of directory which contains the source files.
        """
        if not os.path.exists(os.path.join(dir_path, 'VBOOTA')) or \
           not os.path.exists(os.path.join(dir_path, 'VBOOTB')) or \
           not os.path.exists(os.path.join(dir_path, 'FVMAIN')) or \
           not os.path.exists(os.path.join(dir_path, 'FVMAINB')):
            raise Exception("Source firmware file(s) doesn't exist.")

        VBOOTA_blob = open(os.path.join(dir_path, 'VBOOTA'), 'rb').read()
        VBOOTB_blob = open(os.path.join(dir_path, 'VBOOTB'), 'rb').read()
        FVMAIN_blob = open(os.path.join(dir_path, 'FVMAIN'), 'rb').read()
        FVMAINB_blob = open(os.path.join(dir_path, 'FVMAINB'), 'rb').read()

        self._bios_handler.set_section_sig('a', VBOOTA_blob,
                                           write_through=True)
        self._bios_handler.set_section_sig('b', VBOOTB_blob,
                                           write_through=True)
        self._bios_handler.set_section_body('a', FVMAIN_blob,
                                            write_through=True)
        self._bios_handler.set_section_body('b', FVMAINB_blob,
                                            write_through=True)


    def dump_EC_firmware(self, ec_path):
        """Dump the current EC firmware to a file, specified by ec_path.

        Args:
            ec_path: The path of the EC image to be written.
        """
        self._ec_handler.dump_whole(ec_path)


    def set_EC_write_protect(self, enable):
        """Enable write protect of the EC flash chip.

        Args:
            enable: True if activating EC write protect. Otherwise, False.
        """
        self._chromeos_interface.log('Requesting set EC write protect to %s' %
                                     ('enable' if enable else 'disable'))
        if enable:
            self._ec_handler.enable_write_protect()
        else:
            self._ec_handler.disable_write_protect()


    def run_cgpt_test_loop(self):
        """Run the CgptState test loop. The tst logic is handled in the client.

        Returns:
            0: there are more cgpt tests to execute.
            1: no more CgptState test, finished.
        """
        return self._cgpt_state.test_loop()


    def set_cgpt_test_step(self, step):
        """Set the CgptState test step.

        Args:
            step: A test step number.
        """
        self._cgpt_state.set_step(step)


    def get_cgpt_test_step(self):
        """Get the CgptState test step.

        Returns:
            A test step number.
        """
        return self._cgpt_state.get_step()


    def setup_firmwareupdate_temp_dir(self, shellball=None):
        """Setup temporary directory.

        Devkeys are copied to _key_path. Then, shellball (default:
        /usr/sbin/chromeos-firmwareupdate) is extracted to _work_path.

        Args:
            shellball: Path of shellball.
        """

        self.cleanup_firmwareupdate_temp_dir()

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
        self.run_shell_command(
            'sh %s --sb_extract %s' % (shellball_path, self._work_path))


    def retrieve_shellball_fwid(self):
        """Retrieve shellball's fwid.

        This method should be called after setup_firmwareupdate_temp_dir.

        Returns:
            Shellball's fwid.
        """
        self.run_shell_command('dump_fmap -x %s %s' %
                                  (os.path.join(self._work_path, 'bios.bin'),
                                   'RW_FWID_A'))

        [fwid] = self.run_shell_command_get_output(
                "cat RW_FWID_A | tr '\\0' '\\t' | cut -f1")

        return fwid


    def cleanup_firmwareupdate_temp_dir(self):
        """Cleanup temporary directory."""
        if os.path.isdir(self._temp_path):
            shutil.rmtree(self._temp_path)


    def repack_firmwareupdate_shellball(self, append):
        """Repack shellball with new fwid.

           New fwid follows the rule: [orignal_fwid]-[append].

        Args:
            append: use for new fwid naming.
        """
        shutil.copy('/usr/sbin/chromeos-firmwareupdate', '%s' %
            os.path.join(self._temp_path,
                         'chromeos-firmwareupdate-%s' % append))

        self.run_shell_command('sh %s  --sb_repack %s' % (
            os.path.join(self._temp_path,
                         'chromeos-firmwareupdate-%s' % append),
            self._work_path))

        args = ['-i']
        args.append('"s/TARGET_FWID=\\"\\(.*\\)\\"/TARGET_FWID=\\"\\1.%s\\"/g"'
                    % append)
        args.append('%s'
                    % os.path.join(self._temp_path,
                                   'chromeos-firmwareupdate-%s' % append))
        cmd = 'sed %s' % ' '.join(args)
        self.run_shell_command(cmd)

        args = ['-i']
        args.append('"s/TARGET_UNSTABLE=\\".*\\"/TARGET_UNSTABLE=\\"\\"/g"')
        args.append('%s'
                    % os.path.join(self._temp_path,
                                   'chromeos-firmwareupdate-%s' % append))
        cmd = 'sed %s' % ' '.join(args)
        self.run_shell_command(cmd)


    def resign_firmware(self, version):
        """Resign firmware with version.

        Args:
            version: new firmware version number.
        """
        args = [os.path.join(self._work_path, 'bios.bin')]
        args.append(os.path.join(self._temp_path, 'output.bin'))
        args.append(os.path.join(self._keys_path, 'firmware_data_key.vbprivk'))
        args.append(os.path.join(self._keys_path, 'firmware.keyblock'))
        args.append(os.path.join(self._keys_path,
                                 'dev_firmware_data_key.vbprivk'))
        args.append(os.path.join(self._keys_path, 'dev_firmware.keyblock'))
        args.append(os.path.join(self._keys_path, 'kernel_subkey.vbpubk'))
        args.append('%d' % version)
        args.append('1')
        cmd = '/usr/share/vboot/bin/resign_firmwarefd.sh %s' % ' '.join(args)
        self.run_shell_command(cmd)

        shutil.copyfile('%s' % os.path.join(self._temp_path, 'output.bin'),
                        '%s' % os.path.join(self._work_path, 'bios.bin'))


    def run_firmware_autoupdate(self, append):
        """Do firmwareupdate with autoupdate mode using new shellball.

        Args:
            append: decide which shellball to use with format
                    chromeos-firmwareupdate-[append]
        """
        self.run_shell_command(
            '/bin/sh %s --mode autoupdate '
            '--noupdate_ec --nocheck_rw_compatible'
                % os.path.join(self._temp_path,
                           'chromeos-firmwareupdate-%s' % append))


    def run_firmware_factory_install(self):
        """ Do firmwareupdate with factory_install mode using new shellball."""
        self.run_shell_command(
            '/bin/sh %s --mode factory_install --noupdate_ec'
            % os.path.join(self._temp_path, 'chromeos-firmwareupdate'))


    def run_firmware_bootok(self, append):
        """Do bootok mode using new shellball.

           Copy firmware B to firmware A if reboot success.
        """
        self.run_shell_command(
            '/bin/sh %s --mode bootok' % os.path.join(self._temp_path,
                    'chromeos-firmwareupdate-%s' % append))


    def run_firmware_recovery(self):
        """Recovery to original shellball."""
        self.run_shell_command(
            '/bin/sh %s --mode recovery --noupdate_ec --nocheck_rw_compatible'
                % os.path.join(self._temp_path, 'chromeos-firmwareupdate'))


    def get_temp_path(self):
        """Get temporary directory path."""
        return self._temp_path


    def get_keys_path(self):
        """Get keys path in temporary directory."""
        return self._keys_path


    def resign_kernel_with_keys(self, section, key_path=None):
        """Resign kernel with temporary key."""
        self._kernel_handler.resign_kernel(section, key_path)


    def create_temp_dir(self, prefix='backup_'):
        """Create a temporary directory and return the path."""
        return tempfile.mkdtemp(prefix=prefix)


    def cleanup(self):
        """Cleanup for the RPC server. Currently nothing."""
        pass


def main():
    parser = OptionParser(usage='Usage: %prog [options]')
    parser.add_option('--port', type='int', dest='port', default=9990,
                      help='port number of XMLRPC server')
    (options, args) = parser.parse_args()

    faft_client = FAFTClient()

    # Launch the XMLRPC server to provide FAFTClient commands.
    server = SimpleXMLRPCServer(('localhost', options.port), allow_none=True,
                                logRequests=True)
    server.register_introspection_functions()
    server.register_instance(faft_client)
    print 'XMLRPC Server: Serving FAFTClient on port %s' % options.port
    server.serve_forever()


if __name__ == '__main__':
    main()
