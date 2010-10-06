#!/usr/bin/python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities to test the autoupdate process.
"""

from autotest_lib.client.common_lib import pexpect, utils
import logging, socket, os, sys, time, urllib2


FACTORY_CONFIG = """
config = [
 {
   'qual_ids': set(["%(platform)s"]),
   'test_image': 'update.gz',
   'test_checksum': '%(checksum)s',
 }
]
"""

CMD_TIMEOUT = 120
DEVSERVER_PORT = 8080


def generate_update_payload(image, dest):
    """Generate update payload.

    Args:
        image: path to image
        dest: output path to generated payload
    """
    logging.info('Generating update payload...')

    image_opt = '--image %s' % image
    dest_opt = '--output %s' % dest

    cmd = ('./cros_generate_update_payload %s %s --patch_kernel'
           % (image_opt, dest_opt))
    output = pexpect.run(cmd, timeout=CMD_TIMEOUT)
    if output.find('Done') > 0:
        logging.info('Payload written to %s' % dest)
    else:
        logging.error('Failed to generate payload: %s' % output)


def extract_image(path, members, dest):
    """Extract members from archive.

    Args:
        path: path to zip archive
        members: members in archive to extract
        dest: output directory
    """
    cmd = 'unzip -qo %s %s -d %s' % (path, members, dest)
    output = pexpect.run(cmd)
    if len(output) != 0:
        raise IOError('Error while extracting %s: %s' % (path, output))


def is_devserver_running():
    localhost = socket.gethostname()
    try:
        resp = urllib2.urlopen('http://%s:%s' % (localhost, DEVSERVER_PORT))
    except urllib2.URLError:
        return False
    if resp is None:
        return False
    return True


def start_devserver(devserver_dir, omaha_config):
    """Start devserver

    Assumes payload is devserver_dir/static/update.gz.

    Args:
        devserver_dir: directory containing devserver.py
        omaha_config: path to omaha config

    Returns:
        pexpect process running devserver
    """
    if is_devserver_running():
        logging.info('Devserver is already running')
        return None

    logging.info('Generating factory config...')
    logging.info('Running devserver...')

    opts = ('--client_prefix ChromeOSUpdateEngine '
            '--factory_config %s' % omaha_config)
    cmd = 'python devserver.py %s' % opts
    devserver = pexpect.spawn(cmd, timeout=CMD_TIMEOUT, cwd=devserver_dir)
    # Wait for devserver to start up.
    time.sleep(10)

    patterns = [str(DEVSERVER_PORT)]
    try:
        index = devserver.expect_exact(patterns)
        if index == 0:
            logging.info('devserver running...')
            logging.info(is_devserver_running())
            return devserver
    except pexpect.EOF:
        raise Exception('EOF')
    except pexpect.TIMEOUT:
        raise Exception('Process timed out')


def make_omaha_config(output_path, platform, payload_path):
    """Make an omaha config file

    Writes config to output.
    Assumes update payload is in ./static.

    Args:
        output_path: path to write config to
        platform: name of platform or 'channel'
        payload_path: path to update payload
    """
    shell_cmd = 'cat %s | openssl sha1 -binary | openssl base64' % payload_path
    process = pexpect.spawn('/bin/bash', ['-c', shell_cmd])
    process.expect(pexpect.EOF)
    checksum = process.before.strip()
    if len(checksum.split('\n')) > 1:
        raise Exception('Could not determine hash for % s' % payload_path)
    values = {}
    values['platform'] = platform
    values['checksum'] = checksum
    config = FACTORY_CONFIG % values
    utils.open_write_close(output_path, config)


def kill_devserver(devserver):
    """Kill chroot of devserver.
    Send interrupt signal to devserver and wait for it to terminate.

    Args:
        devserver: pexpect process running devserver
    """
    if devserver.isalive():
        devserver.sendintr()
        devserver.wait()

