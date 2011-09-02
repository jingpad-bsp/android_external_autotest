# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Exposes the FAFTClient interface over XMLRPC.

It launches a XMLRPC server and exposes the interface of FAFTClient object.
The FAFTClient object aggreates some useful functions of exisintg SAFT
libraries.
"""

import os
import sys
import tempfile
from optparse import OptionParser
from SimpleXMLRPCServer import SimpleXMLRPCServer

# Import libraries from SAFT.
sys.path.append('/usr/sbin/firmware/saft')
import chromeos_interface
import flashrom_handler
import kernel_handler
import saft_flashrom_util
import tpm_handler


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
        tmp_dir = tempfile.mkdtemp()

        # TODO(waihong): Move the explicit object.init() methods to the
        # objects' constructors (ChromeOSInterface, FlashromHandler,
        # KernelHandler, and TpmHandler).
        self._chromeos_interface = chromeos_interface.ChromeOSInterface(False)
        self._chromeos_interface.init(tmp_dir)

        self._flashrom_handler = flashrom_handler.FlashromHandler()
        self._flashrom_handler.init(saft_flashrom_util,
                                    self._chromeos_interface)
        self._flashrom_handler.new_image()

        self._kernel_handler = kernel_handler.KernelHandler()
        self._kernel_handler.init(self._chromeos_interface)

        self._tpm_handler = tpm_handler.TpmHandler()
        self._tpm_handler.init(self._chromeos_interface)


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


    def set_try_fw_b(self):
        """Set 'Try Frimware B' flag in crossystem."""
        self._chromeos_interface.log('Requesting restart with firmware B')
        self._chromeos_interface.cs.fwb_tries = 1


    def corrupt_firmware(self, section):
        """Corrupt the requested firmware section.

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Corrupting firmware %s' % section)
        self._flashrom_handler.corrupt_firmware(section)


    def restore_firmware(self, section):
        """Restore the requested firmware section (previously corrupted).

        Args:
            section: A firmware section, either 'a' or 'b'.
        """
        self._chromeos_interface.log('Restoring firmware %s' % section)
        self._flashrom_handler.restore_firmware(section)


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
    server = SimpleXMLRPCServer(('localhost', options.port), allow_none=True)
    server.register_introspection_functions()
    server.register_instance(faft_client)
    print 'XMLRPC Server: Serving FAFTClient on port %s' % options.port
    server.serve_forever()


if __name__ == '__main__':
    main()
