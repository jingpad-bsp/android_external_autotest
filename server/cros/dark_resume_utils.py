# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

POWER_DIR = '/var/lib/power_manager'
TMP_POWER_DIR = '/tmp/power_manager'
POWER_DEFAULTS = '/usr/share/power_manager/board_specific'


def dark_resume_setup(host):
    """Set up powerd preferences so we will properly go into dark resume,
    and still be able to communicate with the DUT.

    @param host: the DUT to set up dark resume for

    """
    logging.info('Setting up dark resume preferences')

    # Make temporary directory, which will be used to hold
    # temporary preferences. We want to avoid writing into
    # /var/lib so we don't have to save any state.
    logging.debug('Creating temporary powerd prefs at %s', TMP_POWER_DIR)
    host.run('mkdir -p %s' % TMP_POWER_DIR)

    logging.debug('Enabling dark resume')
    host.run('echo 0 > %s/disable_dark_resume' % TMP_POWER_DIR)

    logging.debug('Enabling USB ports in dark resume')

    dev_contents = host.run('cat %s/dark_resume_devices' % POWER_DEFAULTS,
                            ignore_status=True).stdout
    dev_list = dev_contents.split('\n')
    new_dev_list = filter(lambda dev: dev.find('usb') == -1, dev_list)
    new_dev_contents = '\n'.join(new_dev_list)
    host.run('echo -e \'%s\' > %s/dark_resume_devices' %
             (new_dev_contents, TMP_POWER_DIR))

    # bind the tmp directory to the power preference directory
    host.run('mount --bind %s %s' % (TMP_POWER_DIR, POWER_DIR))

    logging.debug('Restarting powerd with new settings')
    host.run('restart powerd')


def dark_resume_teardown(host):
    """Clean up changes made by dark_resume_setup.

    @param host: the DUT to remove dark resume prefs for

    """
    logging.info('Tearing down dark resume preferences')

    logging.debug('Cleaning up temporary powerd bind mounts')
    host.run('umount %s' % POWER_DIR, ignore_status=True)

    logging.debug('Restarting powerd to revert to old settings')
    host.run('restart powerd')
