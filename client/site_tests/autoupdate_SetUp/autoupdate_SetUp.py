# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time
from autotest_lib.client.bin import test, utils

ROOTFS_LSB_RELEASE = '/etc/lsb-release'
STATEFUL_LSB_RELEASE = '/mnt/stateful_partition/etc/lsb-release'

class autoupdate_SetUp(test.test):
    version = 1

    def _override_lsb_release(self, devserver):
        """Override the lsb-release with one in the stateful partition
        """
        auserver_key = 'CHROMEOS_AUSERVER'
        board_key = 'CHROMEOS_RELEASE_BOARD'
        devserver_key = 'CHROMEOS_DEVSERVER'
        track_key = 'CHROMEOS_RELEASE_TRACK'

        if not devserver.startswith('http'):
            devserver = 'http://%s' % devserver

        new_auserver_value = '%s/update' % devserver
        new_board_value = 'autest'
        new_devserver_value = devserver
        new_track_value = 'test-channel'

        # Create initial lsb-release file in stateful partition.
        comment = '# Override %s and %s on %s' % (auserver_key,
                                                  devserver_key,
                                                  time.asctime())
        utils.write_one_line(STATEFUL_LSB_RELEASE, comment)

        # Read and override auserver and devserver values.
        lsb_release = utils.read_keyval(ROOTFS_LSB_RELEASE)
        lsb_release[auserver_key] = new_auserver_value
        lsb_release[board_key] = new_board_value
        lsb_release[devserver_key] = new_devserver_value
        lsb_release[track_key] = new_track_value

        utils.write_keyval(STATEFUL_LSB_RELEASE, lsb_release)
        logging.info('Current release: % s' % lsb_release['GOOGLE_RELEASE'])

    def run_once(self, devserver):
        self._override_lsb_release(devserver)
