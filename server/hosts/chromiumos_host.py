import httplib
import logging
import socket
import urlparse

from autotest_lib.client.common_lib import error
from autotest_lib.server import autoserv_parser
from autotest_lib.server.hosts import base_classes

parser = autoserv_parser.autoserv_parser
STATEFULDEV_UPDATER='/usr/local/bin/stateful_update'
UPDATER_BIN='/opt/google/memento_updater/memento_updater.sh'
UPDATER_CONFIG='/etc/lsb-release'


class ChromiumOSError(error.AutotestError):
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
        # TODO(seano): Retrieve softwareupdate.log from target host.
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

        logging.info('Installing from %s to: %s' % (update_url, self.hostname))

        # First, attempt dev & test tools update (which don't live on
        # the rootfs). This must succeed so that the newly installed
        # host is testable after we run the autoupdater.
        statefuldev_cmd = ' '.join([STATEFULDEV_UPDATER, update_url])
        logging.info(statefuldev_cmd)
        try:
            self.run(statefuldev_cmd, timeout=300)
        except error.AutoservRunError, e:
            raise ChromiumOSError('stateful_update failed on %s',
                                  self.hostname)

        # Run autoupdate command. This tells the autoupdate process on
        # the host to look for an update at a specific URL and version
        # string.
        autoupdate_cmd = ' '.join([UPDATER_BIN, '--omaha_url=%s' % update_url,
                          '--force_update'])
        logging.info(autoupdate_cmd)
        try:
           self.run('rm -f /tmp/mememto_complete') # Ignore previous updates.
           self.run(autoupdate_cmd, timeout=600)
        except error.AutoservRunError, e:
            raise ChromiumOSError('OS Updater failed on %s', self.hostname)

        # Check that the installer completed as expected.
        # TODO(seano) verify installer completed in logs.
        #validate_cmd = ''
        #try:
        #    self.run(validate_cmd)
        #except error.AutoservRunError, e:
        #    raise ChromiumOSError('Updater failed on host %s', self.hostname)
        # Updater has returned. reboot.
        self.reboot(timeout=30, wait=True)
        # TODO(seano): verify that image version is in fact running,
        # after reboot.
        # if self.get_build_id() != expected_version:
        #     raise ChromiumOSError('Updater faild on host %s', self.hostname)


    def get_build_id(self):
        """Turns the CHROMEOS_RELEASE_DESCRIPTION into a string that
        matches the build ID."""
        # TODO(seano): handle dev build naming schemes.
        version = self.run('grep CHROMEOS_RELEASE_DESCRIPTION'
                                  ' /etc/lsb-release').stdout
        build_re = (r'CHROMEOS_RELEASE_DESCRIPTION='
                    '(\d+\.\d+\.\d+\.\d+) \(\w+ \w+ (\w+)(.*)\)')
        version_match = version_string.match(build_re, version)
        if not version_match:
            # If we don't find a recognizeable build version, just fail.
            raise ChromiumOSError('build ID not found on %s. ', self.hostname)
        version, build_id, builder = version_match.groups()
        # Continuous builds have an extra "builder number" on the end.
        # Report it if this looks like one.
        build_match = re.match(r'.*: (\d+)', builder)
        if build_match:
            builder_num = '-%s' % build_match.group(1)
        else:
            builder_num = ''
        return '%s-%s%s' % (version, build_id, builder_num)


    def reset(self):
        """Reboots the machine."""
        try:
            self.reboot(wait=False)
        except error.AutoservRunError:
            # TODO(seano): figure out possible hard resets.
            raise
