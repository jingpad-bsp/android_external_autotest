# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import httplib
import logging
import multiprocessing
import os
import re
import urlparse
import urllib2

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, global_config
from autotest_lib.client.common_lib.cros import dev_server

# Local stateful update path is relative to the CrOS source directory.
LOCAL_STATEFUL_UPDATE_PATH = 'src/platform/dev/stateful_update'
LOCAL_CHROOT_STATEFUL_UPDATE_PATH = '/usr/bin/stateful_update'
REMOTE_STATEUL_UPDATE_PATH = '/usr/local/bin/stateful_update'
STATEFUL_UPDATE = '/tmp/stateful_update'
UPDATER_BIN = '/usr/bin/update_engine_client'
UPDATER_IDLE = 'UPDATE_STATUS_IDLE'
UPDATER_NEED_REBOOT = 'UPDATE_STATUS_UPDATED_NEED_REBOOT'
UPDATED_MARKER = '/var/run/update_engine_autoupdate_completed'
UPDATER_LOGS = ['/var/log/messages', '/var/log/update_engine']
# A list of update engine client states that occur after an update is triggered.
UPDATER_PROCESSING_UPDATE = ['UPDATE_STATUS_CHECKING_FORUPDATE',
                             'UPDATE_STATUS_UPDATE_AVAILABLE',
                             'UPDATE_STATUS_DOWNLOADING',
                             'UPDATE_STATUS_FINALIZING']

class ChromiumOSError(error.InstallError):
    """Generic error for ChromiumOS-specific exceptions."""
    pass


class RootFSUpdateError(ChromiumOSError):
    """Raised when the RootFS fails to update."""
    pass


class StatefulUpdateError(ChromiumOSError):
    """Raised when the stateful partition fails to update."""
    pass


def url_to_version(update_url):
    """Return the version based on update_url.

    @param update_url: url to the image to update to.

    """
    # The Chrome OS version is generally the last element in the URL. The only
    # exception is delta update URLs, which are rooted under the version; e.g.,
    # http://.../update/.../0.14.755.0/au/0.14.754.0. In this case we want to
    # strip off the au section of the path before reading the version.
    return re.sub('/au/.*', '',
                  urlparse.urlparse(update_url).path).split('/')[-1].strip()


def url_to_image_name(update_url):
    """Return the image name based on update_url.

    From a URL like:
        http://172.22.50.205:8082/update/lumpy-release/R27-3837.0.0
    return lumpy-release/R27-3837.0.0

    @param update_url: url to the image to update to.
    @returns a string representing the image name in the update_url.

    """
    return '/'.join(urlparse.urlparse(update_url).path.split('/')[-2:])


def _get_devserver_build_from_update_url(update_url):
    """Get the devserver and build from the update url.

    @param update_url: The url for update.
        Eg: http://devserver:port/update/build.

    @return: A tuple of (devserver url, build) or None if the update_url
        doesn't match the expected pattern.

    @raises ValueError: If the update_url doesn't match the expected pattern.
    @raises ValueError: If no global_config was found, or it doesn't contain an
        image_url_pattern.
    """
    pattern = global_config.global_config.get_config_value(
            'CROS', 'image_url_pattern', type=str, default='')
    if not pattern:
        raise ValueError('Cannot parse update_url, the global config needs '
                'an image_url_pattern.')
    re_pattern = pattern.replace('%s', '(\S+)')
    parts = re.search(re_pattern, update_url)
    if not parts or len(parts.groups()) < 2:
        raise ValueError('%s is not an update url' % update_url)
    return parts.groups()


def list_image_dir_contents(update_url):
    """Lists the contents of the devserver for a given build/update_url.

    @param update_url: An update url. Eg: http://devserver:port/update/build.
    """
    if not update_url:
        logging.warning('Need update_url to list contents of the devserver.')
        return
    error_msg = 'Cannot check contents of devserver, update url %s' % update_url
    try:
        devserver_url, build = _get_devserver_build_from_update_url(update_url)
    except ValueError as e:
        logging.warning('%s: %s', error_msg, e)
        return
    devserver = dev_server.ImageServer(devserver_url)
    try:
        devserver.list_image_dir(build)
    # The devserver will retry on URLError to avoid flaky connections, but will
    # eventually raise the URLError if it persists. All HTTPErrors get
    # converted to DevServerExceptions.
    except (dev_server.DevServerException, urllib2.URLError) as e:
        logging.warning('%s: %s', error_msg, e)


class ChromiumOSUpdater():
    """Helper class used to update DUT with image of desired version."""
    KERNEL_A = {'name': 'KERN-A', 'kernel': 2, 'root': 3}
    KERNEL_B = {'name': 'KERN-B', 'kernel': 4, 'root': 5}
    # Time to wait for new kernel to be marked successful after
    # auto update.
    KERNEL_UPDATE_TIMEOUT = 120


    def __init__(self, update_url, host=None, local_devserver=False):
        self.host = host
        self.update_url = update_url
        self._update_error_queue = multiprocessing.Queue(2)
        self.local_devserver = local_devserver
        if not local_devserver:
          self.update_version = url_to_version(update_url)
        else:
          self.update_version = None

    def check_update_status(self):
        """Return current status from update-engine."""
        update_status = self._run(
            '%s -status 2>&1 | grep CURRENT_OP' % UPDATER_BIN)
        return update_status.stdout.strip().split('=')[-1]


    def reset_update_engine(self):
        """Restarts the update-engine service."""
        self._run('rm -f %s' % UPDATED_MARKER)
        try:
            self._run('initctl stop update-engine')
        except error.AutoservRunError:
            logging.warning('Stopping update-engine service failed. Already dead?')
        self._run('initctl start update-engine')

        if self.check_update_status() != UPDATER_IDLE:
            raise ChromiumOSError('%s is not in an installable state' %
                                  self.host.hostname)


    def _run(self, cmd, *args, **kwargs):
        """Abbreviated form of self.host.run(...)"""
        return self.host.run(cmd, *args, **kwargs)


    def rootdev(self, options=''):
        """Returns the stripped output of rootdev <options>.

        @param options: options to run rootdev.

        """
        return self._run('rootdev %s' % options).stdout.strip()


    def get_kernel_state(self):
        """Returns the (<active>, <inactive>) kernel state as a pair."""
        active_root = int(re.findall('\d+\Z', self.rootdev('-s'))[0])
        if active_root == self.KERNEL_A['root']:
            return self.KERNEL_A, self.KERNEL_B
        elif active_root == self.KERNEL_B['root']:
            return self.KERNEL_B, self.KERNEL_A
        else:
            raise ChromiumOSError('Encountered unknown root partition: %s' %
                                  active_root)


    def _cgpt(self, flag, kernel, dev='$(rootdev -s -d)'):
        """Return numeric cgpt value for the specified flag, kernel, device. """
        return int(self._run('cgpt show -n -i %d %s %s' % (
            kernel['kernel'], flag, dev)).stdout.strip())


    def get_kernel_priority(self, kernel):
        """Return numeric priority for the specified kernel.

        @param kernel: information of the given kernel, KERNEL_A or KERNEL_B.

        """
        return self._cgpt('-P', kernel)


    def get_kernel_success(self, kernel):
        """Return boolean success flag for the specified kernel.

        @param kernel: information of the given kernel, KERNEL_A or KERNEL_B.

        """
        return self._cgpt('-S', kernel) != 0


    def get_kernel_tries(self, kernel):
        """Return tries count for the specified kernel.

        @param kernel: information of the given kernel, KERNEL_A or KERNEL_B.

        """
        return self._cgpt('-T', kernel)


    def get_stateful_update_script(self):
        """Returns the path to the stateful update script on the target."""
        # We attempt to load the local stateful update path in 3 different
        # ways. First we use the location specified in the autotest global
        # config. If this doesn't exist, we attempt to use the Chromium OS
        # Chroot path to the installed script. If all else fails, we use the
        # stateful update script on the host.
        stateful_update_path = os.path.join(
                global_config.global_config.get_config_value(
                        'CROS', 'source_tree', default=''),
                LOCAL_STATEFUL_UPDATE_PATH)

        if not os.path.exists(stateful_update_path):
            logging.warning('Could not find Chrome OS source location for '
                         'stateful_update script at %s, falling back to chroot '
                         'copy.', stateful_update_path)
            stateful_update_path = LOCAL_CHROOT_STATEFUL_UPDATE_PATH

        if not os.path.exists(stateful_update_path):
            logging.warning('Could not chroot stateful_update script, falling '
                         'back on client copy.')
            statefuldev_script = REMOTE_STATEUL_UPDATE_PATH
        else:
            self.host.send_file(
                    stateful_update_path, STATEFUL_UPDATE, delete_dest=True)
            statefuldev_script = STATEFUL_UPDATE

        return statefuldev_script


    def reset_stateful_partition(self):
        """Clear any pending stateful update request."""
        statefuldev_cmd = [self.get_stateful_update_script()]
        statefuldev_cmd += ['--stateful_change=reset', '2>&1']
        self._run(' '.join(statefuldev_cmd))


    def revert_boot_partition(self):
        """Revert the boot partition."""
        part = self.rootdev('-s')
        logging.warning('Reverting update; Boot partition will be %s', part)
        return self._run('/postinst %s 2>&1' % part)


    def trigger_update(self):
        """Triggers a background update on a test image.

        @raise RootFSUpdateError if anything went wrong.

        """
        autoupdate_cmd = '%s --check_for_update --omaha_url=%s' % (
            UPDATER_BIN, self.update_url)
        logging.info('Triggering update via: %s', autoupdate_cmd)
        try:
            self._run(autoupdate_cmd)
        except (error.AutoservSshPermissionDeniedError,
                error.AutoservSSHTimeout) as e:
            raise RootFSUpdateError('SSH on %s is seeing %s' %
                                    (self.host.hostname, type(e).__name__))
        except error.AutoservRunError as e:

            # Check if the exit code is 255, if so it's probably a generic
            # SSH error.
            result = e.args[1]
            if result.exit_status == 255:
              raise RootFSUpdateError('SSH on %s is seeing a generic error.' %
                                      self.host.hostname)

            # We have ruled out all SSH cases, the error code is from
            # update_engine_client, though we still don't know why.
            list_image_dir_contents(self.update_url)
            raise RootFSUpdateError(
                    'devserver unreachable, payload unavailable, '
                    'or AU bug (unlikely) on %s: %s' %
                    (self.host.hostname, type(e).__name__))


    def _verify_update_completed(self):
        """Verifies that an update has completed.

        @raise RootFSUpdateError: if verification fails.
        """
        status = self.check_update_status()
        if status != UPDATER_NEED_REBOOT:
            raise RootFSUpdateError('Update did not complete with correct '
                                    'status. Expecting %s, actual %s' %
                                            (UPDATER_NEED_REBOOT, status))


    def rollback_rootfs(self, powerwash):
        """Triggers rollback and waits for it to complete.

        @param powerwash: If true, powerwash as part of rollback.

        @raise RootFSUpdateError if anything went wrong.

        """
        version = self.get_build_id()
        # Introduced can_rollback in M36 (build 5772). # etc/lsb-release matches
        # X.Y.Z. This version split just pulls the first part out.
        try:
            build_number = int(version.split('.')[0])
        except ValueError:
            logging.error('Could not parse build number.')
            build_number = 0

        if build_number >= 5772:
            can_rollback_cmd = '%s --can_rollback' % (UPDATER_BIN)
            logging.info('Checking for rollback.')
            try:
                self._run(can_rollback_cmd)
            except error.AutoservRunError as e:
                raise RootFSUpdateError("Rollback isn't possible on %s: %s" %
                                        (self.host.hostname, str(e)))

        rollback_cmd = '%s --rollback --follow' % (UPDATER_BIN)
        if not powerwash:
          rollback_cmd += ' --nopowerwash'

        logging.info('Performing rollback.')
        try:
            self._run(rollback_cmd)
        except error.AutoservRunError as e:
            raise RootFSUpdateError('Rollback failed on %s: %s' %
                                    (self.host.hostname, str(e)))

        self._verify_update_completed()


    def update_rootfs(self):
        """Updates the rootfs partition only."""
        logging.info('Updating root partition...')

        # Run update_engine using the specified URL.
        try:
            autoupdate_cmd = '%s --update --omaha_url=%s 2>&1' % (
                UPDATER_BIN, self.update_url)
            self._run(autoupdate_cmd, timeout=900)
        except error.AutoservRunError:
            list_image_dir_contents(self.update_url)
            update_error = RootFSUpdateError('update-engine failed on %s' %
                                             self.host.hostname)
            self._update_error_queue.put(update_error)
            raise update_error

        try:
            self._verify_update_completed()
        except RootFSUpdateError as e:
            self._update_error_queue.put(e)
            raise


    def update_stateful(self, clobber=True):
        """Updates the stateful partition.

        @param clobber: If True, a clean stateful installation.
        """
        logging.info('Updating stateful partition...')
        statefuldev_url = self.update_url.replace('update',
                                                  'static')

        # Attempt stateful partition update; this must succeed so that the newly
        # installed host is testable after update.
        statefuldev_cmd = [self.get_stateful_update_script(), statefuldev_url]
        if clobber:
            statefuldev_cmd.append('--stateful_change=clean')

        statefuldev_cmd.append('2>&1')
        try:
            self._run(' '.join(statefuldev_cmd), timeout=600)
        except error.AutoservRunError:
            update_error = StatefulUpdateError('stateful_update failed on %s' %
                                               self.host.hostname)
            self._update_error_queue.put(update_error)
            raise update_error


    def run_update(self, force_update, update_root=True):
        """Update the DUT with image of specific version.

        @param force_update: True to update DUT even if it's running the same
            version already.
        @param update_root: True to force a kernel update. If it's False and
            force_update is True, stateful update will be used to clean up
            the DUT.

        """
        booted_version = self.get_build_id()
        if (self.check_version() and not force_update):
            logging.info('System is already up to date. Skipping update.')
            return False

        if self.update_version:
            logging.info('Updating from version %s to %s.',
                         booted_version, self.update_version)

        # Check that Dev Server is accepting connections (from autoserv's host).
        # If we can't talk to it, the machine host probably can't either.
        auserver_host = urlparse.urlparse(self.update_url)[1]
        try:
            httplib.HTTPConnection(auserver_host).connect()
        except IOError:
            raise ChromiumOSError(
                'Update server at %s not available' % auserver_host)

        logging.info('Installing from %s to %s', self.update_url,
                     self.host.hostname)

        # Reset update state.
        self.reset_update_engine()
        self.reset_stateful_partition()

        try:
            updaters = [
                multiprocessing.process.Process(target=self.update_rootfs),
                multiprocessing.process.Process(target=self.update_stateful)
                ]
            if not update_root:
                logging.info('Root update is skipped.')
                updaters = updaters[1:]

            # Run the updaters in parallel.
            for updater in updaters: updater.start()
            for updater in updaters: updater.join()

            # Re-raise the first error that occurred.
            if not self._update_error_queue.empty():
                update_error = self._update_error_queue.get()
                self.revert_boot_partition()
                self.reset_stateful_partition()
                raise update_error

            logging.info('Update complete.')
            return True
        except:
            # Collect update engine logs in the event of failure.
            if self.host.job:
                logging.info('Collecting update engine logs...')
                self.host.get_file(
                    UPDATER_LOGS, self.host.job.sysinfo.sysinfodir,
                    preserve_perm=False)
            list_image_dir_contents(self.update_url)
            raise
        finally:
            self.host.show_update_engine_log()


    def check_version(self):
        """Check the image running in DUT has the desired version.

        @returns: True if the DUT's image version matches the version that
            the autoupdater tries to update to.

        """
        booted_version = self.get_build_id()
        return (self.update_version and
                self.update_version.endswith(booted_version))


    def check_version_to_confirm_install(self):
        """Check image running in DUT has the desired version to be installed.

        The method should not be used to check if DUT needs to have a full
        reimage. Only use it to confirm a image is installed.

        The method is designed to verify version for following 4 scenarios with
        samples of version to update to and expected booted version:
        1. trybot paladin build.
        update version: trybot-lumpy-paladin/R27-3837.0.0-b123
        booted version: 3837.0.2013_03_21_1340

        2. trybot release build.
        update version: trybot-lumpy-release/R27-3837.0.0-b456
        booted version: 3837.0.0

        3. buildbot official release build.
        update version: lumpy-release/R27-3837.0.0
        booted version: 3837.0.0

        4. non-official paladin rc build.
        update version: lumpy-paladin/R27-3878.0.0-rc7
        booted version: 3837.0.0-rc7

        5. chrome-perf build.
        update version: lumpy-chrome-perf/R28-3837.0.0-b2996
        booted version: 3837.0.0

        6. pgo-generate build.
        update version: lumpy-release-pgo-generate/R28-3837.0.0-b2996
        booted version: 3837.0.0-pgo-generate

        When we are checking if a DUT needs to do a full install, we should NOT
        use this method to check if the DUT is running the same version, since
        it may return false positive for a DUT running trybot paladin build to
        be updated to another trybot paladin build.

        TODO: This logic has a bug if a trybot paladin build failed to be
        installed in a DUT running an older trybot paladin build with same
        platform number, but different build number (-b###). So to conclusively
        determine if a tryjob paladin build is imaged successfully, we may need
        to find out the date string from update url.

        @returns: True if the DUT's image version (without the date string if
            the image is a trybot build), matches the version that the
            autoupdater is trying to update to.

        """
        # In the local_devserver case, we can't know the expected
        # build, so just pass.
        if not self.update_version:
            return True

        # Always try the default check_version method first, this prevents
        # any backward compatibility issue.
        if self.check_version():
            return True

        # Remove R#- and -b# at the end of build version
        stripped_version = re.sub(r'(R\d+-|-b\d+)', '', self.update_version)

        booted_version = self.get_build_id()

        is_trybot_paladin_build = re.match(r'.+trybot-.+-paladin',
                                           self.update_url)

        # Replace date string with 0 in booted_version
        booted_version_no_date = re.sub(r'\d{4}_\d{2}_\d{2}_\d+', '0',
                                        booted_version)
        has_date_string = booted_version != booted_version_no_date

        is_pgo_generate_build = re.match(r'.+-pgo-generate',
                                           self.update_url)

        # Remove |-pgo-generate| in booted_version
        booted_version_no_pgo = booted_version.replace('-pgo-generate', '')
        has_pgo_generate = booted_version != booted_version_no_pgo

        if is_trybot_paladin_build:
            if not has_date_string:
                logging.error('A trybot paladin build is expected. Version ' +
                              '"%s" is not a paladin build.', booted_version)
                return False
            return stripped_version == booted_version_no_date
        elif is_pgo_generate_build:
            if not has_pgo_generate:
                logging.error('A pgo-generate build is expected. Version ' +
                              '"%s" is not a pgo-generate build.',
                              booted_version)
                return False
            return stripped_version == booted_version_no_pgo
        else:
            if has_date_string:
                logging.error('Unexpected date found in a non trybot paladin' +
                              ' build.')
                return False
            # Versioned build, i.e., rc or release build.
            return stripped_version == booted_version


    def get_build_id(self):
        """Pulls the CHROMEOS_RELEASE_VERSION string from /etc/lsb-release."""
        return self._run('grep CHROMEOS_RELEASE_VERSION'
                         ' /etc/lsb-release').stdout.split('=')[1].strip()


    def verify_boot_expectations(self, expected_kernel_state, rollback_message):
        """Verifies that we fully booted given expected kernel state.

        This method both verifies that we booted using the correct kernel
        state and that the OS has marked the kernel as good.

        @param expected_kernel_state: kernel state that we are verifying with
            i.e. I expect to be booted onto partition 4 etc. See output of
            get_kernel_state.
        @param rollback_message: string to raise as a ChromiumOSError
            if we booted with the wrong partition.

        @raises ChromiumOSError: If we didn't.
        """
        # Figure out the newly active kernel.
        active_kernel_state = self.get_kernel_state()[0]

        # Check for rollback due to a bad build.
        if (expected_kernel_state and
                active_kernel_state != expected_kernel_state):

            # Kernel crash reports should be wiped between test runs, but
            # may persist from earlier parts of the test, or from problems
            # with provisioning.
            #
            # Kernel crash reports will NOT be present if the crash happened
            # before encrypted stateful is mounted.
            #
            # TODO(dgarrett): Integrate with server/crashcollect.py at some
            # point.
            kernel_crashes = glob.glob('/var/spool/crash/kernel.*.kcrash')
            if kernel_crashes:
                rollback_message += ': kernel_crash'
                logging.debug('Found %d kernel crash reports:',
                              len(kernel_crashes))
                # The crash names contain timestamps that may be useful:
                #   kernel.20131207.005945.0.kcrash
                for crash in kernel_crashes:
                  logging.debug('  %s', os.path.basename(crash))

            # Print out some information to make it easier to debug
            # the rollback.
            logging.debug('Dumping partition table.')
            self._run('cgpt show $(rootdev -s -d)')
            logging.debug('Dumping crossystem for firmware debugging.')
            self._run('crossystem --all')
            raise ChromiumOSError(rollback_message)

        # Make sure chromeos-setgoodkernel runs.
        try:
            utils.poll_for_condition(
                lambda: (self.get_kernel_tries(active_kernel_state) == 0
                         and self.get_kernel_success(active_kernel_state)),
                exception=ChromiumOSError(),
                timeout=self.KERNEL_UPDATE_TIMEOUT, sleep_interval=5)
        except ChromiumOSError:
            services_status = self._run('status system-services').stdout
            if services_status != 'system-services start/running\n':
                event = ('Chrome failed to reach login screen')
            else:
                event = ('update-engine failed to call '
                         'chromeos-setgoodkernel')
            raise ChromiumOSError(
                    'After update and reboot, %s '
                    'within %d seconds' % (event,
                                           self.KERNEL_UPDATE_TIMEOUT))
