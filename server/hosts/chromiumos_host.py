import logging
import socket
from urlparse import urljoin

from autotest_lib.client.common_lib import error
from autotest_lib.server import autoserv_parser
from autotest_lib.server.hosts import base_classes


parser = autoserv_parser.autoserv_parser

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


    def machine_install(self, update_url=None, biosflash=None):
        image = parser.options.image
        version_string = None
        if image:
            #TODO(seano): set version, deal with blank version elsewhere
            logging.info('Install %s to host: %s' % (image, self.hostname))
            version_string = image
        else:
            logging.info('Install %s to host: %s' % ('latest', self.hostname))

        if not update_url:
            # Assume we're running the mock autoupdate server on the
            # autotest host.
            update_url = 'http://%s:8080/update' % socket.gethostname()
        # The mock autoupdater in devserver has been modified to
        # accept an additional url under /update/VERSION
        if version_string:
            update_url = urljoin(update_url, 'update/%s' % version_string)

        # Prepare to host a update image.
        # Check that a devserver is available on our preferred URL.
        # Check that requested image version exists.

        # Run autoupdate command. This tells the autoupdate process on
        # the host to look for an update at a specific URL and version
        # string.

        # TODO(seano): remove reconfig_cmd, change autoupdate_cmd to use
        # memento_updater's flags
        autoupdate_cmd = [UPDATER_BIN, '--omaha_url=%s' % update_url,
                          '--force_update']
        try:
            cmd = ' '.join(autoupdate_cmd)
            logging.info(cmd)
            self.run(cmd)
        except error.AutoservRunError, e:
            raise ChromiumOSError('OS Updater failed on %s', self.hostname)
        # Now, check that the installer completed as expected.
        try:
            cmd = ''
            #self.run(cmd)
        except error.AutoservRunError, e:
            raise ChromiumOSError('Failed to install OS image to host %s',
                                  self.hostname)
        # Updater has returned. reboot.
        self.reboot(timeout=30, wait=True)
        # TODO(seano): verify that image version is in fact installed,
        # after reboot.


    def reset(self):
        """Reboots the machine."""
        try:
            self.reboot(wait=False)
        except error.AutoservRunError:
            # TODO(seano): figure out possible hard resets.
            raise
