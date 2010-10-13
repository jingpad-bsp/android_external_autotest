#!/usr/bin/python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities to test the autoupdate process.
"""

from autotest_lib.client.common_lib import pexpect, utils
import logging, socket, os, sys, time, urllib2

DEVSERVER_PORT = 8080

CMD_TIMEOUT = 120
FACTORY_CONFIG = """
config = [
  {
    'qual_ids': set(["%(platform)s"]),
    'test_image': 'update.gz',
    'test_checksum': '%(checksum)s',
  }
]
"""

CWD = os.getcwd()
DEVSERVER_SRC = os.path.join('/home', os.environ['USER'], 'trunk',
                             'src', 'platform', 'dev')
DEVSERVER_DIR = os.path.join(CWD, 'dev')
PAYLOAD_PATH = os.path.join(DEVSERVER_DIR, 'static', 'update.gz')

class AutoUpdateTester():

    def __init__(self, image_path):
        """Copy devserver source into current working directory.
        """
        self.image_path = image_path
        os.system('cp -r %s %s' % (DEVSERVER_SRC, CWD))


    def assert_is_file(self, path):
        if not os.path.isfile(path):
            raise error.TestError('%s is not a file' % path)


    def generate_update_payload(self):
        """Generate update payload.
        """
        logging.info('Generating update payload...')

        self.assert_is_file(self.image_path)
        image_opt = '--image %s' % self.image_path 
        dest_opt = '--output %s' % PAYLOAD_PATH 

        cmd = ('./cros_generate_update_payload %s %s --patch_kernel'
               % (image_opt, dest_opt))
        output = pexpect.run(cmd, timeout=CMD_TIMEOUT)
        if output.find('Done') > 0:
            logging.info('Payload written to %s' % PAYLOAD_PATH)
        else:
            logging.error('Failed to generate payload: %s' % output)


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

        logging.info('Generating factory config...')
        omaha_config = self.make_omaha_config('autest')

        logging.info('Running devserver...')

        opts = ('--client_prefix ChromeOSUpdateEngine '
                '--factory_config %s' % omaha_config)
        cmd = 'python devserver.py %s' % opts
        devserver = pexpect.spawn(cmd, timeout=CMD_TIMEOUT, cwd=DEVSERVER_DIR)
        # Wait for devserver to start up.
        time.sleep(10)

        patterns = [str(DEVSERVER_PORT)]
        try:
            index = devserver.expect_exact(patterns)
            if index == 0:
                logging.info('devserver running...')
                logging.info(self.is_devserver_running())
                return devserver
        except pexpect.EOF:
            raise Exception('EOF')
        except pexpect.TIMEOUT:
            raise Exception('Process timed out')


    def make_omaha_config(self, platform):
        """Make an Omaha config file.

        Writes config to output.
        Assumes update payload is in ./static.

        Args:
            platform: name of platform or 'channel'.
        """
        new_config_path = os.path.join(DEVSERVER_DIR, 'autest.conf')
        shell_cmd = 'cat %s | openssl sha1 -binary | openssl base64' % PAYLOAD_PATH
        process = pexpect.spawn('/bin/bash', ['-c', shell_cmd])
        process.expect(pexpect.EOF)
        checksum = process.before.strip()
        if len(checksum.split('\n')) > 1:
            raise Exception('Could not determine hash for % s' % PAYLOAD_PATH)
        values = {}
        values['platform'] = platform
        values['checksum'] = checksum
        config = FACTORY_CONFIG % values
        utils.open_write_close(new_config_path, config)
        return new_config_path


    def kill_devserver(self, devserver):
        """Kill chroot of devserver.
        Send interrupt signal to devserver and wait for it to terminate.

        Args:
            devserver: pexpect process running devserver.
        """
        if devserver.isalive():
            devserver.sendintr()
            devserver.wait()

