# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Description:
#
# Here are unit tests for the python class SynClient (not third-party program
# synclient).  These tests should be ran when you are changing
# factory_Touchpad.py.
#
# Tests here do not depend on synclient or any thing that are on the target
# machine.  Files under the directory mock/ provides a minimal environment for
# SynClient to be ran on any machine.
#
# You may run these tests on host machine:
# $ python test_factory_Touchpad.py

import unittest
import re
import sys
sys.path.append('mock')
import factory_Touchpad

from itertools import count, izip

TestError = factory_Touchpad.error.TestError
TestNAError = factory_Touchpad.error.TestNAError

FIELDS = ['LeftEdge', 'RightEdge', 'TopEdge',
          'BottomEdge', 'FingerLow', 'FingerHigh']

def assertRaisesRegexp(self, exc, regexp, callable, *args):
    # assertRaisesRegexp appears in Python 2.7
    # this method should be removed once we upgrade to it
    try:
        callable(*args)
    except exc as e:
        self.assert_(re.search(regexp, str(e)) is not None,
                     'Regex "%s" mismatch string "%s"' % (regexp, e))
    else:
        self.assert_(False, "No exception raised")

def make_echo(message):
    echo = sum([line.split() + ['\n'] for line in message.split('\n')], [])
    return "echo -ne '%s'" % ' '.join(echo)

class TestSynClient(unittest.TestCase):
    '''Here we test SynClient.__init__() for two major parts:
subprocess invocation and parsing "synclient -l" output.

There are two subprocess invocations to be tested:

The first invocation (calling "synclient -l"), we mock the command line
and check if it fails when there is no such command or when the command
fails:
    test_no_such_command_1, test_command_fail_1

The second invocation (calling "synclient -m 50") we mock the command line
and check if it fails when there is no such command or when the command
fails/terminates immediately:
    test_no_such_command_2, test_command_fail_2, test_command_terminate_2

There are two tests for the parsing "syclient -l" output:

The first tests if proper exception is raised when any required field is
missing:
    test_missing_field

The second tests if proper exception is raised when any field has inproper
format:
    test_invalid_format
'''

    def setUp(self):
        args = ('%s = %d' % (k, i) for i, k in izip(count(), FIELDS))
        self.echo_cmd = make_echo(' \\n '.join(args))

        # a command that should exist and succeed on all hosts
        self.dummy_cmd = '/bin/ls'

        # a command that should exist but failed on all hosts
        self.failed_cmd = '/bin/cat no-such-file'

        self.backup_settings_cmd = factory_Touchpad._SYNCLIENT_SETTINGS_CMDLINE
        self.backup_cmd = factory_Touchpad._SYNCLIENT_CMDLINE

    def test_no_such_command_1(self):
        no_such_cmd = 'no-such-command-settings -a -b -c'
        factory_Touchpad._SYNCLIENT_SETTINGS_CMDLINE = no_such_cmd
        factory_Touchpad._SYNCLIENT_CMDLINE = self.dummy_cmd
        assertRaisesRegexp(self, TestError,
                           r'^Failure on "%s" \[127\]$' % no_such_cmd,
                           factory_Touchpad.SynClient, None)

    def test_command_fail_1(self):
        factory_Touchpad._SYNCLIENT_SETTINGS_CMDLINE = self.failed_cmd
        factory_Touchpad._SYNCLIENT_CMDLINE = self.dummy_cmd
        assertRaisesRegexp(self, TestError,
                           r'^Failure on "%s" \[1\]$' % self.failed_cmd,
                           factory_Touchpad.SynClient, None)

    def test_no_such_command_2(self):
        no_such_cmd = 'no-such-command -a -b -c'
        factory_Touchpad._SYNCLIENT_SETTINGS_CMDLINE = self.echo_cmd
        factory_Touchpad._SYNCLIENT_CMDLINE = no_such_cmd
        assertRaisesRegexp(self, TestError,
                           r'^Failure on launching "%s"$' % no_such_cmd,
                           factory_Touchpad.SynClient, None)

    def test_command_fail_2(self):
        factory_Touchpad._SYNCLIENT_SETTINGS_CMDLINE = self.echo_cmd
        factory_Touchpad._SYNCLIENT_CMDLINE = self.failed_cmd
        assertRaisesRegexp(self, TestError,
                           r'^Failure on "%s" \[1\]$' % self.failed_cmd,
                           factory_Touchpad.SynClient, None)

    def test_command_terminate_2(self):
        factory_Touchpad._SYNCLIENT_SETTINGS_CMDLINE = self.echo_cmd
        factory_Touchpad._SYNCLIENT_CMDLINE = self.dummy_cmd
        assertRaisesRegexp(self, TestError,
                           r'^Termination unexpected on "%s"$' %
                           self.dummy_cmd,
                           factory_Touchpad.SynClient, None)

    def test_missing_field(self):
        for i in xrange(len(FIELDS)):
            fields = FIELDS[:i] + FIELDS[i+1:] # strip FIELDS[i]
            args = ('%s = %f' % (k, j/3.0) for j, k in izip(count(), fields))
            self.echo_cmd = make_echo(' \\n '.join(args))
            factory_Touchpad._SYNCLIENT_SETTINGS_CMDLINE = self.echo_cmd
            factory_Touchpad._SYNCLIENT_CMDLINE = self.dummy_cmd
            assertRaisesRegexp(self, TestNAError,
                               r'^Can\'t detect all hardware information$',
                               factory_Touchpad.SynClient, None)

    def test_invalid_format(self):
        for i in xrange(len(FIELDS)):
            args = ('%s = xxx' % k if i == j else '%s = %f' % (k, j/3.0)
                    for j, k in izip(count(), FIELDS))
            self.echo_cmd = make_echo(' \\n '.join(args))
            factory_Touchpad._SYNCLIENT_SETTINGS_CMDLINE = self.echo_cmd
            factory_Touchpad._SYNCLIENT_CMDLINE = self.dummy_cmd
            assertRaisesRegexp(self, TestNAError,
                               r'^Can\'t understand all hardware information$',
                               factory_Touchpad.SynClient, None)

    def tearDown(self):
        factory_Touchpad._SYNCLIENT_SETTINGS_CMDLINE = self.backup_settings_cmd
        factory_Touchpad._SYNCLIENT_CMDLINE = self.backup_cmd

if __name__ == '__main__':
    unittest.main()
