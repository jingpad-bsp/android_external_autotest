#!/usr/bin/python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities to test the autoupdate process.
"""

from autotest_lib.client.common_lib import error, pexpect, utils
import logging, socket, os, sys, time, urllib2

DEVSERVER_PORT = 8080

CMD_TIMEOUT = 120

CWD = os.getcwd()
DEVSERVER_SRC = os.path.join('/home', os.environ['USER'], 'trunk',
                             'src', 'platform', 'dev')
DEVSERVER_DIR = os.path.join(CWD, 'dev')

class AutoUpdateTester():

    def __init__(self, image_path):
        """Copy devserver source into current working directory.
        """
        self.image_path = image_path
        os.system('cp -r %s %s' % (DEVSERVER_SRC, CWD))

    def is_devserver_running(self):
        localhost = socket.gethostname()
        try:
            resp = urllib2.urlopen('http://%s:%s' % (localhost, DEVSERVER_PORT))
        except urllib2.URLError:
            return False
        if resp is None:
            return False
        return True


    def start_devserver(self):
        """Start devserver

        Assumes payload is $PWD/dev/static/update.gz.

        Returns:
            pexpect process running devserver.
        """

        if self.is_devserver_running():
            logging.info('Devserver is already running')
            raise error.TestFail('Please kill devserver before running test.')

        logging.info('Starting devserver...')

        opts = ('--client_prefix ChromeOSUpdateEngine '
                '--image %s' % self.image_path)
        cmd = 'python devserver.py %s' % opts
        devserver = pexpect.spawn(cmd, timeout=CMD_TIMEOUT, cwd=DEVSERVER_DIR)
        # Wait for devserver to start up.
        time.sleep(10)

        patterns = [str(DEVSERVER_PORT)]
        try:
            index = devserver.expect_exact(patterns)
            if index == 0:
                if self.is_devserver_running():
                  logging.info('devserver is running...')
                  return devserver
                else:
                  raise Exception('Could not start devserver')
        except pexpect.EOF:
            raise Exception('EOF')
        except pexpect.TIMEOUT:
            raise Exception('Process timed out')

    def kill_devserver(self, devserver):
        """Kill chroot of devserver.
        Send interrupt signal to devserver and wait for it to terminate.

        Args:
            devserver: pexpect process running devserver.
        """
        if devserver.isalive():
            devserver.sendintr()
            devserver.wait()

