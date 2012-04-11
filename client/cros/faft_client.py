# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Exposes the FAFTClient interface over XMLRPC.

It launches a XMLRPC server and exposes the interface of FAFTClient object.
The FAFTClient object aggreates some useful functions of exisintg SAFT
libraries.
"""

import functools, os, shutil, sys
from optparse import OptionParser
from SimpleXMLRPCServer import SimpleXMLRPCServer

# Import libraries from SAFT.
sys.path.append('/usr/local/sbin/firmware/saft')
import cgpt_state, chromeos_interface, flashrom_handler, kernel_handler
import saft_flashrom_util, tpm_handler


def allow_multiple_section_input(image_operator):
    @functools.wraps(image_operator)
    def wrapper(self, section):
        if type(section) in (tuple, list):
            for sec in section:
                image_operator(self, sec)
        else:
            image_operator(self, section)
    return wrapper


class FAFTClient(object):
    """A class of FAFT client which aggregates some useful functions of SAFT.

    This class can be exposed via a XMLRPC server such that its functions can
    be accessed remotely.

    Attributes:
        _chromeos_interface: An object to encapsulate OS services functions.
        _flashrom_handler: An object to automate flashrom testing.
        _kernel_handler: An object to provide kernel related actions.
        _tpm_handler: An object to control TPM device.
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

        self._flashrom_handler = flashrom_handler.FlashromHandler()
        self._flashrom_handler.init(saft_flashrom_util,
                                    self._chromeos_interface,
                                    None,
                                    '/usr/share/vboot/devkeys')
        self._flashrom_handler.new_image()

        self._kernel_handler = kernel_handler.KernelHandler()
        # TODO(waihong): The dev_key_path is a new argument. We do that in
        # order not to break the old image and still be able to run.
        try:
            self._kernel_handler.init(self._chromeos_interface,
                                      dev_key_path='/usr/share/vboot/devkeys')
        except:
            # Copy the key to the current working directory.
            shutil.copy('/usr/share/vboot/devkeys/kernel_data_key.vbprivk', '.')
            self._kernel_handler.init(self._chromeos_interface)

        self._tpm_handler = tpm_handler.TpmHandler()
        self._tpm_handler.init(self._chromeos_interface)

        self._cgpt_state = cgpt_state.CgptState(
                'AUTO', self._chromeos_interface, self.get_root_dev())


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
        return self._chromeos_interface.run_shell_command_get_output(
                'mosys platform name')[0]


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


    def get_gbb_flags(self):
        """Get the GBB flags.

        Returns:
            An integer of the GBB flags.
        """
        self._chromeos_interface.log('Getting GBB flags')
        return self._flashrom_handler.get_gbb_flags()


    def get_firmware_flags(self, section):
        """Get the preamble flags of a firmware section.

        Args:
            section: A firmware section, either 'a' or 'b'.

        Returns:
            An integer of the preamble flags.
        """
        self._chromeos_interface.log('Getting preamble flags of firmware %s' %
                                     section)
        return self._flashrom_handler.get_section_flags(section)


    @allow_multiple_section_input
    def corrupt_firmware(self, section):
        """Corrupt the requested firmware section signature.

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Corrupting firmware signature %s' %
                                     section)
        self._flashrom_handler.corrupt_firmware(section)


    @allow_multiple_section_input
    def corrupt_firmware_body(self, section):
        """Corrupt the requested firmware section body.

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Corrupting firmware body %s' %
                                     section)
        self._flashrom_handler.corrupt_firmware_body(section)


    @allow_multiple_section_input
    def restore_firmware(self, section):
        """Restore the previously corrupted firmware section signature.

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Restoring firmware signature %s' %
                                     section)
        self._flashrom_handler.restore_firmware(section)


    @allow_multiple_section_input
    def restore_firmware_body(self, section):
        """Restore the previously corrupted firmware section body.

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Restoring firmware body %s' %
                                     section)
        self._flashrom_handler.restore_firmware_body(section)


    def _modify_firmware_version(self, section, delta):
        """Modify firmware version for the requested section, by adding delta.

        The passed in delta, a positive or a negative number, is added to the
        original firmware version.
        """
        original_version = self._flashrom_handler.get_section_version(section)
        new_version = original_version + delta
        flags = self._flashrom_handler.get_section_flags(section)
        self._chromeos_interface.log(
                'Setting firmware section %s version from %d to %d' % (
                section, original_version, new_version))
        self._flashrom_handler.set_section_version(section, new_version, flags,
                                             write_through=True)

    @allow_multiple_section_input
    def move_firmware_backward(self, section):
        """Decrement firmware version for the requested section."""
        self._modify_firmware_version(section, -1)


    @allow_multiple_section_input
    def move_firmware_forward(self, section):
        """Increase firmware version for the requested section."""
        self._modify_firmware_version(section, 1)


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
        self._chromeos_interface.log('restoring kernel %s' % section)
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
                                logRequests=False)
    server.register_introspection_functions()
    server.register_instance(faft_client)
    print 'XMLRPC Server: Serving FAFTClient on port %s' % options.port
    server.serve_forever()


if __name__ == '__main__':
    main()
