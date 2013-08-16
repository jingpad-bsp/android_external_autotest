#!/usr/bin/env python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cmd
import dbus
import dbus.exceptions

import mm1


class PseudoModemClient(cmd.Cmd):
    """
    Interactive client for PseudoModemManager.

    """
    def __init__(self):
        cmd.Cmd.__init__(self)
        self.prompt = '> '
        self._bus = dbus.SystemBus()

    def _get_proxy(self, path=mm1.TESTING_PATH):
        return self._bus.get_object(mm1.I_MODEM_MANAGER, path)

    def Begin(self):
        """
        Starts the interactive shell.

        """
        print '\nWelcome to the PseudoModemManager shell!\n'
        self.cmdloop()

    def can_exit(self):
        """Override"""
        return True

    def do_properties(self, args):
        """
        Handles the 'properties' command.

        @param args: Arguments to the command. Unused.

        """
        if args:
            print '\nCommand "properties" expects no arguments.\n'
            return
        try:
            props = self._get_proxy().GetAll(
                            mm1.I_TESTING,
                            dbus_interface=mm1.I_PROPERTIES)
            print '\nProperties: '
            for k, v in props.iteritems():
                print '   ' + k + ': ' + str(v)
            print
        except dbus.exceptions.DBusException as e:
            print ('\nAn error occurred while communicating with '
                   'PseudoModemManager: ' + e.get_dbus_name() + ' - ' +
                   e.message + '\n')
        return False

    def help_properties(self):
        """Handles the 'help properties' command."""
        print '\nReturns the properties under the testing interface.\n'

    def do_sms(self, args):
        """
        Simulates a received SMS.

        @param args: A string containing the sender and the text message
                content, in which everything before the first ' ' character
                belongs to the sender and everything else belongs to the
                message content. For example "Gandalf You shall not pass!"
                will be parsed into:

                    sender="Gandalf"
                    content="You shall not pass!"

                Pseudomodem doesn't distinguish between phone numbers and
                strings containing non-numeric characters for the sender field
                so args can contain pretty much anything.

        """
        arglist = args.split(' ', 1)
        if len(arglist) != 2:
            print '\nMalformed SMS args: ' + args + '\n'
            return
        try:
            self._get_proxy().ReceiveSms(
                    arglist[0], arglist[1], dbus_interface=mm1.I_TESTING)
            print '\nSMS sent!\n'
        except dbus.exceptions.DBusException as e:
            print ('\nAn error occurred while communicating with '
                   'PseudoModemManager: ' + e.get_dbus_name() + ' - ' +
                   e.message + '\n')
        return False

    def help_sms(self):
        """Handles the 'help sms' command."""
        print '\nUsage: sms <sender phone #> <message text>\n'


    def do_set(self, args):
        """
        Handles various commands that start with 'set'.

        @param args: Defines the set command to be issued and its
                arguments. Currently supported commands are:

                  set pco <pco-value>

        """
        arglist = args.split(' ')
        if len(arglist) < 1:
            print '\nInvalid command: set ' + args + '\n'
            return
        if arglist[0] == 'pco':
            if len(arglist) == 1:
                arglist.append('')
            elif len(arglist) != 2:
                print '\nExpected: pco <pco-value>. Found: ' + args + '\n'
                return
            pco_value = arglist[1]
            try:
                self._get_proxy().UpdatePcoInfo(
                        pco_value, dbus_interface=mm1.I_TESTING)
                print '\nPCO value updated!\n'
            except dbus.exceptions.DBusException as e:
                print ('\nAn error occurred while communicating with '
                       'PseudoModemManager: ' + e.get_dbus_name() + ' - ' +
                       e.message + '\n')
        else:
            print '\nUnknown command: set ' + args + '\n'
        return False


    def help_set(self):
        """Handles the 'help set' command."""
        print ('\nUsage: set pco <pco-value>\n<pco-value> can be empty to set'
               ' the PCO value to an empty string.\n')


    def do_exit(self, args):
        """
        Handles the 'exit' command.

        @param args: Arguments to the command. Unused.

        """
        if args:
            print '\nCommand "exit" expects no arguments.\n'
            return
        resp = raw_input('Are you sure? (yes/no): ')
        if resp == 'yes':
            print '\nGoodbye!\n'
            return True
        if resp != 'no':
            print '\nDid not understand: ' + resp + '\n'
        return False

    def help_exit(self):
        """Handles the 'help exit' command."""
        print ('\nExits the interpreter. Shuts down the pseudo modem manager '
               'if the interpreter was launched by running pseudomodem.py')

    do_EOF = do_exit
    help_EOF = help_exit

def main():
    """
    main method, run when this module is executed as stand-alone.

    """
    client = PseudoModemClient()
    client.Begin()

if __name__ == '__main__':
    main()
