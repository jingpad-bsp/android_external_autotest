# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import logging
import re
import socket
import urlparse

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants as chromeos_constants

STATEFULDEV_UPDATER = '/usr/local/bin/stateful_update'
UPDATER_BIN = '/usr/bin/update_engine_client'
UPDATER_IDLE = 'UPDATE_STATUS_IDLE'
UPDATER_NEED_REBOOT = 'UPDATE_STATUS_UPDATED_NEED_REBOOT'
UPDATED_MARKER = '/var/run/update_engine_autoupdate_completed'


class ChromiumOSError(error.InstallError):
    """Generic error for ChromiumOS-specific exceptions."""
    pass


def url_to_version(update_url):
    # The ChromiumOS updater respects the last element in the path as
    # the requested version. Parse it out.
    return urlparse.urlparse(update_url).path.split('/')[-1]


class ChromiumOSUpdater():
    def __init__(self, host=None, update_url=None):
        self.host = host
        self.update_url = update_url
        self.update_version = url_to_version(update_url)


    def check_update_status(self):
        update_status_cmd = ' '.join([UPDATER_BIN, '-status', '2>&1',
                                      '| grep CURRENT_OP'])
        update_status = self._run(update_status_cmd)
        return update_status.stdout.strip().split('=')[-1]


    def reset_update_engine(self):
        logging.info('Resetting update-engine.')
        self._run('rm -f %s' % UPDATED_MARKER)
        try:
            self._run('initctl stop update-engine')
        except error.AutoservRunError, e:
            logging.warn('Stopping update-engine service failed. Already dead?')
        self._run('initctl start update-engine')
        # May need to wait if service becomes slow to restart.
        if self.check_update_status() != UPDATER_IDLE:
            raise ChromiumOSError('%s is not in an installable state' %
                                  self.host.hostname)


    def _run(self, cmd, *args, **kwargs):
        return self.host.run(cmd, *args, **kwargs)


    def rootdev(self):
        return self._run('rootdev').stdout.strip()


    def revert_boot_partition(self):
        part = self.rootdev()
        logging.warn('Reverting update; Boot partition will be %s', part)
        return self._run('/postinst %s 2>&1' % part)


    def run_update(self):
        if not self.update_url:
            return False

        # Check that devserver is accepting connections (from autoserv's host)
        # If we can't talk to it, the machine host probably can't either.
        auserver_host = urlparse.urlparse(self.update_url)[1]
        try:
            httplib.HTTPConnection(auserver_host).connect()
        except socket.error:
            raise ChromiumOSError('Update server at %s not available' %
                                  auserver_host)

        logging.info('Installing from %s to: %s' % (self.update_url,
                                                    self.host.hostname))
        # Reset update_engine's state & check that update_engine is idle.
        self.reset_update_engine()

        # Run autoupdate command. This tells the autoupdate process on
        # the host to look for an update at a specific URL and version
        # string.
        autoupdate_cmd = ' '.join([UPDATER_BIN,
                                   '--update',
                                   '--omaha_url=%s' % self.update_url,
                                   ' 2>&1'])
        logging.info(autoupdate_cmd)
        try:
            self._run(autoupdate_cmd, timeout=900)
        except error.AutoservRunError, e:
            # Either a runtime error occurred on the host, or
            # update_engine_client exited with > 0.
            raise ChromiumOSError('update_engine failed on %s' %
                                  self.host.hostname)

        # Check that the installer completed as expected.
        status = self.check_update_status()
        if status != UPDATER_NEED_REBOOT:
            raise ChromiumOSError('update-engine error on %s: '
                                  '"%s" from update-engine' %
                                  (self.host.hostname, status))

        # Attempt dev & test tools update (which don't live on the
        # rootfs). This must succeed so that the newly installed host
        # is testable after we run the autoupdater.
        statefuldev_url = self.update_url.replace('update', 'static/archive')

        statefuldev_cmd = ' '.join([STATEFULDEV_UPDATER, statefuldev_url,
                                    '2>&1'])
        logging.info(statefuldev_cmd)
        try:
            self._run(statefuldev_cmd, timeout=600)
        except error.AutoservRunError, e:
            # TODO(seano): If statefuldev update failed, we must mark
            # the update as failed, and keep the same rootfs after
            # reboot.
            self.revert_boot_partition()
            raise ChromiumOSError('stateful_update failed on %s.' %
                                  self.host.hostname)
        return True


    def check_version(self):
        booted_version = self.get_build_id()
        if not booted_version:
            booted_version = self.get_dev_build_id()
        if not booted_version in self.update_version:
            logging.error('Expected Chromium OS version: %s.'
                          'Found Chromium OS %s',
                          self.update_version, booted_version)
            raise ChromiumOSError('Updater failed on host %s' %
                                  self.host.hostname)
        else:
            return True


    def get_build_id(self):
        """Turns the CHROMEOS_RELEASE_DESCRIPTION into a string that
        matches the build ID."""
        version = self._run('grep CHROMEOS_RELEASE_DESCRIPTION'
                            ' /etc/lsb-release').stdout
        build_re = (r'CHROMEOS_RELEASE_DESCRIPTION='
                    '(\d+\.\d+\.\d+\.\d+) \(\w+ \w+ (\w+)(.*)\)')
        version_match = re.match(build_re, version)
        if version_match:
            version, build_id, builder = version_match.groups()
            build_match = re.match(r'.*: (\d+)', builder)
            if build_match:
                builder_num = '-b%s' % build_match.group(1)
            else:
                builder_num = ''
            return '%s-r%s%s' % (version, build_id, builder_num)


    def get_dev_build_id(self):
        """Pulls the CHROMEOS_RELEASE_VERSION string from /etc/lsb-release."""
        return self._run('grep CHROMEOS_RELEASE_VERSION'
                         ' /etc/lsb-release').stdout.split('=')[1].strip()
