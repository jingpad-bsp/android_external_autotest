# Copyright 2009 Google Inc. Released under the GPL v2

"""
This file contains the implementation of a host object for the local machine.
"""

import httplib, glob, logging, os, platform, socket, urlparse
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, hosts


STATEFULDEV_UPDATER='/usr/local/bin/stateful_update'
UPDATER_BIN='/opt/google/memento_updater/memento_updater.sh'
UPDATER_CONFIG='/etc/lsb-release'

class LocalHost(hosts.Host):
    def _initialize(self, hostname=None, bootloader=None, *args, **dargs):
        super(LocalHost, self)._initialize(*args, **dargs)

        # hostname will be an actual hostname when this client was created
        # by an autoserv process
        if not hostname:
            hostname = platform.node()
        self.hostname = hostname
        self.bootloader = bootloader


    def wait_up(self, timeout=None):
        # a local host is always up
        return True


    def run(self, command, timeout=3600, ignore_status=False,
            stdout_tee=utils.TEE_TO_LOGS, stderr_tee=utils.TEE_TO_LOGS,
            stdin=None, args=()):
        """
        @see common_lib.hosts.Host.run()
        """
        try:
            result = utils.run(
                command, timeout=timeout, ignore_status=True,
                stdout_tee=stdout_tee, stderr_tee=stderr_tee, stdin=stdin,
                args=args)
        except error.CmdError, e:
            # this indicates a timeout exception
            raise error.AutotestHostRunError('command timed out', e.result_obj)

        if not ignore_status and result.exit_status > 0:
            raise error.AutotestHostRunError('command execution error', result)

        return result


    def list_files_glob(self, path_glob):
        """
        Get a list of files on a remote host given a glob pattern path.
        """
        return glob.glob(path_glob)


    def machine_install(self, update_url=None):
        if not update_url:
            return False

        # Check that devserver is accepting connections (from autoserv's host)
        # If we can't talk to it, the machine host probably can't either.
        auserver_host = urlparse.urlparse(update_url)[1]
        try:
            httplib.HTTPConnection(auserver_host).connect()
        except socket.error:
            raise error.InstallError('Update server at %s not available' %
                                     auserver_host)

        logging.info('Installing from %s to: %s' % (update_url, self.hostname))

        # First, attempt dev & test tools update (which don't live on
        # the rootfs). This must succeed so that the newly installed
        # host is testable after we run the autoupdater.
        statefuldev_cmd = ' '.join([STATEFULDEV_UPDATER, update_url])
        logging.info(statefuldev_cmd)
        try:
            self.run(statefuldev_cmd, timeout=1200)
        except error.AutoservRunError, e:
            raise error.InstallError('stateful_update failed on %s',
                                     self.hostname)

        # Run autoupdate command. This tells the autoupdate process on
        # the host to look for an update at a specific URL and version
        # string.
        autoupdate_cmd = ' '.join([UPDATER_BIN, '--omaha_url=%s' % update_url,
                          '--force_update'])
        logging.info(autoupdate_cmd)
        try:
           self.run('rm -f /tmp/mememto_complete') # Ignore previous updates.
           self.run(autoupdate_cmd, timeout=1200)
        except error.AutoservRunError, e:
            raise error.InstallError('OS Updater failed on %s', self.hostname)

        # Check that the installer completed as expected.
        # TODO(seano) verify installer completed in logs.


    def symlink_closure(self, paths):
        """
        Given a sequence of path strings, return the set of all paths that
        can be reached from the initial set by following symlinks.

        @param paths: sequence of path strings.
        @return: a sequence of path strings that are all the unique paths that
                can be reached from the given ones after following symlinks.
        """
        paths = set(paths)
        closure = set()

        while paths:
            path = paths.pop()
            if not os.path.exists(path):
                continue
            closure.add(path)
            if os.path.islink(path):
                link_to = os.path.join(os.path.dirname(path),
                                       os.readlink(path))
                if link_to not in closure:
                    paths.add(link_to)

        return closure
