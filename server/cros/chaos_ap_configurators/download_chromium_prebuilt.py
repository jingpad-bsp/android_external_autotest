# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import socket
import subprocess

from autotest_lib.client.common_lib import error

# Absolute path from INSIDE chroot.
DOWNLOAD_PATH = '/tmp/chromium-webdriver-parts'
WEBDRIVER = 'chromedriver'


class WebdriverDownloadError(Exception):
    """Base class for exceptions in this module."""
    pass


def _webdriver_is_installed():
    """Checks for presence of required webdriver binary inside chroot.

    @returns a boolean: True iff the binary is present.
    """
    webdriver_path = os.path.join(DOWNLOAD_PATH, WEBDRIVER)
    if not os.path.exists(webdriver_path):
        logging.error('Missing webdriver binary %r.', webdriver_path)
        return False
    logging.info('Located webdriver binary inside chroot.')
    return True


def _webdriver_is_running():
    """Checks if webdriver binary is running.

    Webdriver binary must be running either on the local machine or in
    the lab as a service.

    Webdriver is expected to run on port 9515. If the port is open, we
    assume webdriver is already running.

    @returns a string: of the address of a successful connection; None
                       if a connection cannot be established.
    """
    # address and port are pulled from establish_driver_connection() in
    # ../chaos_ap_configurators/ap_configurator.py
    servers = ['127.0.0.1', 'atlantis4.mtv.corp.google.com']
    port = 9515
    # Create a TCP socket
    for address in servers:
        s = socket.socket()
        logging.debug('Attempt to connect to %s:%s', address, port)
        try:
            s.connect((address, port))
            logging.info('Connected to %s:%s. Assuming webdriver '
                         'is already running', address, port)
            s.close()
            return address
        except socket.error, e:
            logging.debug('Connection to %s:%s failed: %r', address, port, e)
    logging.debug('No available webdriver service found.')
    return None


def download_chromium_prebuilt_binaries():
    """Downloads and installs webdriver binary inside chroot.

    @raises IOError: if error fetching prebuilt binaries.
    """

    # FIXME(tgao): this is a temporary hack until we completely and cleanly
    #              deprecates use of PyAuto across the board.
    fetch_prebuilt = os.path.join(os.path.dirname(__file__),
        '..', 'chaos_lib', 'fetch_prebuilt_pyauto.py')
    logging.info('Attempt to locate: %s', fetch_prebuilt)
    if not os.path.exists(fetch_prebuilt):
        err = ('Unable to locate script to fetch prebuilt binaries: %s' %
               fetch_prebuilt)
        raise WebdriverDownloadError(err)

    cmds = ['/usr/bin/python', fetch_prebuilt, '-d', DOWNLOAD_PATH, '-l']
    if subprocess.call(cmds, shell=False) != 0:
        err = ('fetch_prebuilt_pyauto.py threw an error, the download '
               'was aborted. Please view stdout for more information.')
        raise WebdriverDownloadError(err)

    logging.info('Successfully downloaded and installed prebuilt binaries to '
                 '%s (inside chroot).', DOWNLOAD_PATH)


def check_webdriver_ready():
    """Checks if webdriver binary is installed and running.

    If it is running, skip install path check. This is needed to run dynamic
    Chaos tests on Autotest drones.

    @returns a string: of the address of webdriver running on port 9515.

    @raises TestError: if failed to download and install webdriver binary.
                       Or if webdriver is installed but not running.
    """
    err = ('Webdriver is installed but not running. From outside chroot, run: '
           '<path to chroot directory>%s/%s' % (DOWNLOAD_PATH, WEBDRIVER))

    server_address = _webdriver_is_running()
    if server_address is not None:
        return server_address

    if not _webdriver_is_installed():
        try:
            download_chromium_prebuilt_binaries()
        except WebdriverDownloadError as e:
            raise error.TestError('Download failed: %s.' % e)

    raise error.TestError(err)
