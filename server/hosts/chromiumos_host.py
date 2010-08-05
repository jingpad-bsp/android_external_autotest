import httplib
import logging
import re
import socket
import urlparse

from autotest_lib.client.bin import site_utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import autoserv_parser
from autotest_lib.server.hosts import base_classes

parser = autoserv_parser.autoserv_parser
STATEFULDEV_UPDATER = '/usr/local/bin/stateful_update'
UPDATER_BIN = '/usr/bin/update_engine_client'
UPDATER_IDLE = 'UPDATE_STATUS_IDLE'
UPDATER_ERROR = 'REPORTING_ERROR_EVENT'
UPDATER_NEED_REBOOT = 'UPDATED_NEED_REBOOT'


class ChromiumOSError(error.InstallError):
    """Generic error for ChromiumOS-specific exceptions."""
    pass


class ChromiumOSHost(base_classes.Host):
    """ChromiumOSHost is a special subclass of SSHHost that supports
    additional install and reboot methods.
    """
    def __initialize(self, hostname, *args, **dargs):
        """
        Construct a ChromiumOSHost object

        Args:
             hostname: network hostname or address of remote machine
        """
        super(ChromiumOSHost, self)._initialize(hostname, *args, **dargs)


    def machine_install(self, update_url=None):
        # TODO(seano): Retrieve update_engine.log from target host.
        # TODO(seano): Once front-end changes are in, Kill this entire
        # cmdline flag; It doesn't match the Autotest workflow.
        if parser.options.image:
            update_url=parser.options.image
        elif not update_url:
            # Assume we're running the mock autoupdate server on the
            # autotest host. Bail if we're not.
            return False

        # Check that devserver is accepting connections (from autoserv's host)
        # If we can't talk to it, the machine host probably can't either.
        auserver_host = urlparse.urlparse(update_url)[1]
        try:
            httplib.HTTPConnection(auserver_host).connect()
        except socket.error:
            raise ChromiumOSError('Update server at %s not available' %
                                  auserver_host)

        # The ChromiumOS updater respects the last element in the path
        # as the requested version. Parse it out.
        update_version = urlparse.urlparse(update_url).path.split('/')[-1]

        logging.info('Installing from %s to: %s' % (update_url, self.hostname))

        self.run('echo "CHROMEOS_DEVSERVER=http://chromeosbuild_server" > '
                 '/mnt/stateful_partition/etc/lsb-release')

        # If we find the system an updated-but-not-rebooted state,
        # that's probably bad and we shouldn't trust that the previous
        # update left the machine in a good state. Reset update_engine's
        # state & ensure that update_engine is idle.
        if self.check_update_status() != UPDATER_IDLE:
            self.run('initctl stop update-engine')
            self.run('rm -f /tmp/update_engine_autoupdate_completed')
            self.run('initctl start update-engine')
            # May need to wait if service becomes slow to restart.
        if self.check_update_status() != UPDATER_IDLE:
            raise ChromiumOSError('%s is not in an installable state' %
                                  self.hostname)

        # First, attempt dev & test tools update (which don't live on
        # the rootfs). This must succeed so that the newly installed
        # host is testable after we run the autoupdater.
        statefuldev_url = urlparse.urljoin(update_url,
            '/static/archive/%s' % update_version)
        statefuldev_cmd = ' '.join([STATEFULDEV_UPDATER, statefuldev_url,
                                    '2>&1'])
        logging.info(statefuldev_cmd)
        try:
            self.run(statefuldev_cmd, timeout=1200)
        except error.AutoservRunError, e:
            raise ChromiumOSError('stateful_update failed on %s',
                                  self.hostname)

        # Run autoupdate command. This tells the autoupdate process on
        # the host to look for an update at a specific URL and version
        # string.
        autoupdate_cmd = ' '.join([UPDATER_BIN, '--omaha_url=%s' % update_url,
                          '--force_update', '-app_version ForcedUpdate'])
        logging.info(autoupdate_cmd)
        try:
            self.run(autoupdate_cmd, timeout=60)
        except error.AutoservRunError, e:
            raise ChromiumOSError('unable to run updater on %s', self.hostname)


        # Check that the installer completed as expected.
        def update_successful():
            status = self.check_update_status()
            if status == UPDATER_IDLE:
                raise ChromiumOSError('update-engine error on %s',
                                      self.hostname)
            else:
                return 'UPDATED_NEED_REBOOT' in status

        site_utils.poll_for_condition(update_successful,
                                      ChromiumOSError('Updater failed'),
                                      900, 10)
        # Updater has returned. reboot.
        self.reboot(timeout=60, wait=True)
        # Following the reboot, verify the correct version.
        booted_version = self.get_build_id()
        if booted_version != update_version:
            logging.info('Expected Chromium OS version: %s' % update_version)
            logging.info('Actual Chromium OS version: %s' % booted_version)
            raise ChromiumOSError('Updater failed on host %s' % self.hostname)


    def check_update_status(self):
        update_status_cmd = ' '.join([UPDATER_BIN, '-status',
                                      '|grep CURRENT_OP'])
        update_status = self.run(update_status_cmd)
        return update_status.stdout.strip().split('=')[-1]


    def get_build_id(self):
        """Turns the CHROMEOS_RELEASE_DESCRIPTION into a string that
        matches the build ID."""
        # TODO(seano): handle dev build naming schemes.
        version = self.run('grep CHROMEOS_RELEASE_DESCRIPTION'
                                  ' /etc/lsb-release').stdout
        build_re = (r'CHROMEOS_RELEASE_DESCRIPTION='
                     '(\d+\.\d+\.\d+\.\d+) \(\w+ \w+ (\w+)(.*)\)')
        version_match = re.match(build_re, version)
        if not version_match:
            raise ChromiumOSError('Unable to get build ID from %s. Found "%s"',
                                  self.hostname, version)
        version, build_id, builder = version_match.groups()
        # Continuous builds have an extra "builder number" on the end.
        # Report it if this looks like one.
        build_match = re.match(r'.*: (\d+)', builder)
        if build_match:
            builder_num = '-b%s' % build_match.group(1)
        else:
            builder_num = ''
        return '%s-r%s%s' % (version, build_id, builder_num)


    def reset(self):
        """Reboots the machine."""
        try:
            self.reboot(wait=False)
        except error.AutoservRunError:
            # TODO(seano): figure out possible hard resets to recovery
            # partition, if reboot fails.
            raise
