# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import re
import time
import urllib2
import urlparse

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server import autotest
from autotest_lib.server import utils as server_utils
from autotest_lib.server.cros.dynamic_suite import constants as ds_constants
from autotest_lib.server.cros.dynamic_suite import tools
from chromite.lib import retry_util

try:
    from chromite.lib import metrics
except ImportError:
    metrics = utils.metrics_mock

try:
    import devserver
    _STATEFUL_UPDATE_PATH = devserver.__path__[0]
except ImportError:
    _STATEFUL_UPDATE_PATH = '/usr/bin'

# Local stateful update path is relative to the CrOS source directory.
UPDATER_IDLE = 'UPDATE_STATUS_IDLE'
UPDATER_NEED_REBOOT = 'UPDATE_STATUS_UPDATED_NEED_REBOOT'
# A list of update engine client states that occur after an update is triggered.
UPDATER_PROCESSING_UPDATE = ['UPDATE_STATUS_CHECKING_FORUPDATE',
                             'UPDATE_STATUS_UPDATE_AVAILABLE',
                             'UPDATE_STATUS_DOWNLOADING',
                             'UPDATE_STATUS_FINALIZING']


_STATEFUL_UPDATE_SCRIPT = 'stateful_update'
_REMOTE_STATEFUL_UPDATE_PATH = os.path.join(
        '/usr/local/bin', _STATEFUL_UPDATE_SCRIPT)
_REMOTE_TMP_STATEFUL_UPDATE = os.path.join(
        '/tmp', _STATEFUL_UPDATE_SCRIPT)

_UPDATER_BIN = '/usr/bin/update_engine_client'
_UPDATER_LOGS = ['/var/log/messages', '/var/log/update_engine']

_KERNEL_A = {'name': 'KERN-A', 'kernel': 2, 'root': 3}
_KERNEL_B = {'name': 'KERN-B', 'kernel': 4, 'root': 5}

# Time to wait for new kernel to be marked successful after
# auto update.
_KERNEL_UPDATE_TIMEOUT = 120


# PROVISION_FAILED - A flag file to indicate provision failures.  The
# file is created at the start of any AU procedure (see
# `ChromiumOSUpdater.run_full_update()`).  The file's location in
# stateful means that on successul update it will be removed.  Thus, if
# this file exists, it indicates that we've tried and failed in a
# previous attempt to update.
PROVISION_FAILED = '/var/tmp/provision_failed'


# A flag file used to enable special handling in lab DUTs.  Some
# parts of the system in Chromium OS test images will behave in ways
# convenient to the test lab when this file is present.  Generally,
# we create this immediately after any update completes.
_LAB_MACHINE_FILE = '/mnt/stateful_partition/.labmachine'


class ChromiumOSError(error.InstallError):
    """Generic error for ChromiumOS-specific exceptions."""


class RootFSUpdateError(ChromiumOSError):
    """Raised when the RootFS fails to update."""


class StatefulUpdateError(ChromiumOSError):
    """Raised when the stateful partition fails to update."""


def _url_to_version(update_url):
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


def _list_image_dir_contents(update_url):
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


# TODO(garnold) This implements shared updater functionality needed for
# supporting the autoupdate_EndToEnd server-side test. We should probably
# migrate more of the existing ChromiumOSUpdater functionality to it as we
# expand non-CrOS support in other tests.
class ChromiumOSUpdater(object):
    """Chromium OS specific DUT update functionality."""

    def __init__(self, update_url, host=None, interactive=True):
        """Initializes the object.

        @param update_url: The URL we want the update to use.
        @param host: A client.common_lib.hosts.Host implementation.
        @param interactive: Bool whether we are doing an interactive update.
        """
        self.update_url = update_url
        self.host = host
        self.interactive = interactive
        self.update_version = _url_to_version(update_url)


    def _run(self, cmd, *args, **kwargs):
        """Abbreviated form of self.host.run(...)"""
        return self.host.run(cmd, *args, **kwargs)


    def check_update_status(self):
        """Returns the current update engine state.

        We use the `update_engine_client -status' command and parse the line
        indicating the update state, e.g. "CURRENT_OP=UPDATE_STATUS_IDLE".
        """
        update_status = self.host.run(command='%s -status | grep CURRENT_OP' %
                                      _UPDATER_BIN)
        return update_status.stdout.strip().split('=')[-1]


    def _rootdev(self, options=''):
        """Returns the stripped output of rootdev <options>.

        @param options: options to run rootdev.

        """
        return self._run('rootdev %s' % options).stdout.strip()


    def get_kernel_state(self):
        """Returns the (<active>, <inactive>) kernel state as a pair."""
        active_root = int(re.findall('\d+\Z', self._rootdev('-s'))[0])
        if active_root == _KERNEL_A['root']:
            return _KERNEL_A, _KERNEL_B
        elif active_root == _KERNEL_B['root']:
            return _KERNEL_B, _KERNEL_A
        else:
            raise ChromiumOSError('Encountered unknown root partition: %s' %
                                  active_root)


    def _cgpt(self, flag, kernel, dev='$(rootdev -s -d)'):
        """Return numeric cgpt value for the specified flag, kernel, device. """
        return int(self._run('cgpt show -n -i %d %s %s' % (
            kernel['kernel'], flag, dev)).stdout.strip())


    def _get_next_kernel(self):
        """Return the kernel that has priority for the next boot."""
        priority_a = self._cgpt('-P', _KERNEL_A)
        priority_b = self._cgpt('-P', _KERNEL_B)
        if priority_a > priority_b:
            return _KERNEL_A
        else:
            return _KERNEL_B


    def _get_kernel_success(self, kernel):
        """Return boolean success flag for the specified kernel.

        @param kernel: information of the given kernel, either _KERNEL_A
            or _KERNEL_B.
        """
        return self._cgpt('-S', kernel) != 0


    def _get_kernel_tries(self, kernel):
        """Return tries count for the specified kernel.

        @param kernel: information of the given kernel, either _KERNEL_A
            or _KERNEL_B.
        """
        return self._cgpt('-T', kernel)


    def _get_last_update_error(self):
        """Get the last autoupdate error code."""
        command_result = self._run(
                 '%s --last_attempt_error' % _UPDATER_BIN)
        return command_result.stdout.strip().replace('\n', ', ')


    def _base_update_handler_no_retry(self, run_args):
        """Base function to handle a remote update ssh call.

        @param run_args: Dictionary of args passed to ssh_host.run function.

        @throws: intercepts and re-throws all exceptions
        """
        try:
            self.host.run(**run_args)
        except Exception as e:
            logging.debug('exception in update handler: %s', e)
            raise e


    def _base_update_handler(self, run_args, err_msg_prefix=None):
        """Handle a remote update ssh call, possibly with retries.

        @param run_args: Dictionary of args passed to ssh_host.run function.
        @param err_msg_prefix: Prefix of the exception error message.
        """
        def exception_handler(e):
            """Examines exceptions and returns True if the update handler
            should be retried.

            @param e: the exception intercepted by the retry util.
            """
            return (isinstance(e, error.AutoservSSHTimeout) or
                    (isinstance(e, error.GenericHostRunError) and
                     hasattr(e, 'description') and
                     (re.search('ERROR_CODE=37', e.description) or
                      re.search('generic error .255.', e.description))))

        try:
            # Try the update twice (arg 2 is max_retry, not including the first
            # call).  Some exceptions may be caught by the retry handler.
            retry_util.GenericRetry(exception_handler, 1,
                                    self._base_update_handler_no_retry,
                                    run_args)
        except Exception as e:
            message = err_msg_prefix + ': ' + str(e)
            raise RootFSUpdateError(message)


    def _wait_for_update_service(self):
        """Ensure that the update engine daemon is running, possibly
        by waiting for it a bit in case the DUT just rebooted and the
        service hasn't started yet.
        """
        def handler(e):
            """Retry exception handler.

            Assumes that the error is due to the update service not having
            started yet.

            @param e: the exception intercepted by the retry util.
            """
            if isinstance(e, error.AutoservRunError):
                logging.debug('update service check exception: %s\n'
                              'retrying...', e)
                return True
            else:
                return False

        # Retry at most three times, every 5s.
        status = retry_util.GenericRetry(handler, 3,
                                         self.check_update_status,
                                         sleep=5)

        # Expect the update engine to be idle.
        if status != UPDATER_IDLE:
            raise ChromiumOSError('%s is not in an installable state' %
                                  self.host.hostname)


    def _reset_update_engine(self):
        """Resets the host to prepare for a clean update regardless of state."""
        self._run('stop ui || true')
        self._run('stop update-engine || true')
        self._run('start update-engine')

        # Wait for update engine to be ready.
        self._wait_for_update_service()


    def _reset_stateful_partition(self):
        """Clear any pending stateful update request."""
        statefuldev_cmd = [self.get_stateful_update_script()]
        statefuldev_cmd += ['--stateful_change=reset', '2>&1']
        self._run(' '.join(statefuldev_cmd))


    def _revert_boot_partition(self):
        """Revert the boot partition."""
        part = self._rootdev('-s')
        logging.warning('Reverting update; Boot partition will be %s', part)
        return self._run('/postinst %s 2>&1' % part)


    def _get_metric_fields(self):
        """Return a dict of metric fields.

        This is used for sending autoupdate metrics for this instance.
        """
        build_name = url_to_image_name(self.update_url)
        try:
            board, build_type, milestone, _ = server_utils.ParseBuildName(
                build_name)
        except server_utils.ParseBuildNameException:
            logging.warning('Unable to parse build name %s for metrics. '
                            'Continuing anyway.', build_name)
            board, build_type, milestone = ('', '', '')
        return {
            'dev_server': dev_server.get_hostname(self.update_url),
            'board': board,
            'build_type': build_type,
            'milestone': milestone,
        }


    def _verify_update_completed(self):
        """Verifies that an update has completed.

        @raise RootFSUpdateError: if verification fails.
        """
        status = self.check_update_status()
        if status != UPDATER_NEED_REBOOT:
            error_msg = ''
            if status == UPDATER_IDLE:
                error_msg = 'Update error: %s' % self._get_last_update_error()
            raise RootFSUpdateError('Update did not complete with correct '
                                    'status. Expecting %s, actual %s. %s' %
                                    (UPDATER_NEED_REBOOT, status, error_msg))


    def trigger_update(self):
        """Triggers a background update.

        @raise RootFSUpdateError or unknown Exception if anything went wrong.
        """
        # If this function is called immediately after reboot (which it is at
        # this time), there is no guarantee that the update service is up and
        # running yet, so wait for it.
        self._wait_for_update_service()

        autoupdate_cmd = ('%s --check_for_update --omaha_url=%s' %
                          (_UPDATER_BIN, self.update_url))
        run_args = {'command': autoupdate_cmd}
        err_prefix = 'Failed to trigger an update on %s. ' % self.host.hostname
        logging.info('Triggering update via: %s', autoupdate_cmd)
        metric_fields = {'success': False}
        try:
            self._base_update_handler(run_args, err_prefix)
            metric_fields['success'] = True
        finally:
            c = metrics.Counter('chromeos/autotest/autoupdater/trigger')
            metric_fields.update(self._get_metric_fields())
            c.increment(fields=metric_fields)


    def update_image(self):
        """Updates the device image and verifies success."""
        autoupdate_cmd = ('%s --update --omaha_url=%s' %
                          (_UPDATER_BIN, self.update_url))
        if not self.interactive:
            autoupdate_cmd = '%s --interactive=false' % autoupdate_cmd
        run_args = {'command': autoupdate_cmd, 'timeout': 3600}
        err_prefix = ('Failed to install device image using payload at %s '
                      'on %s. ' % (self.update_url, self.host.hostname))
        logging.info('Updating image via: %s', autoupdate_cmd)
        metric_fields = {'success': False}
        try:
            self._base_update_handler(run_args, err_prefix)
            metric_fields['success'] = True
        finally:
            c = metrics.Counter('chromeos/autotest/autoupdater/update')
            metric_fields.update(self._get_metric_fields())
            c.increment(fields=metric_fields)
        self._verify_update_completed()


    def get_stateful_update_script(self):
        """Returns the path to the stateful update script on the target.

        When runnning test_that, stateful_update is in chroot /usr/sbin,
        as installed by chromeos-base/devserver packages.
        In the lab, it is installed with the python module devserver, by
        build_externals.py command.

        If we can find it, we hope it exists already on the DUT, we assert
        otherwise.
        """
        stateful_update_file = os.path.join(_STATEFUL_UPDATE_PATH,
                                            _STATEFUL_UPDATE_SCRIPT)
        if os.path.exists(stateful_update_file):
            self.host.send_file(
                    stateful_update_file, _REMOTE_TMP_STATEFUL_UPDATE,
                    delete_dest=True)
            return _REMOTE_TMP_STATEFUL_UPDATE

        if self.host.path_exists(_REMOTE_STATEFUL_UPDATE_PATH):
            logging.warning('Could not chroot %s script, falling back on %s',
                            _STATEFUL_UPDATE_SCRIPT,
                            _REMOTE_STATEFUL_UPDATE_PATH)
            return _REMOTE_STATEFUL_UPDATE_PATH
        else:
            raise ChromiumOSError('Could not locate %s' %
                                  _STATEFUL_UPDATE_SCRIPT)


    def rollback_rootfs(self, powerwash):
        """Triggers rollback and waits for it to complete.

        @param powerwash: If true, powerwash as part of rollback.

        @raise RootFSUpdateError if anything went wrong.

        """
        version = self.host.get_release_version()
        # Introduced can_rollback in M36 (build 5772). # etc/lsb-release matches
        # X.Y.Z. This version split just pulls the first part out.
        try:
            build_number = int(version.split('.')[0])
        except ValueError:
            logging.error('Could not parse build number.')
            build_number = 0

        if build_number >= 5772:
            can_rollback_cmd = '%s --can_rollback' % _UPDATER_BIN
            logging.info('Checking for rollback.')
            try:
                self._run(can_rollback_cmd)
            except error.AutoservRunError as e:
                raise RootFSUpdateError("Rollback isn't possible on %s: %s" %
                                        (self.host.hostname, str(e)))

        rollback_cmd = '%s --rollback --follow' % _UPDATER_BIN
        if not powerwash:
            rollback_cmd += ' --nopowerwash'

        logging.info('Performing rollback.')
        try:
            self._run(rollback_cmd)
        except error.AutoservRunError as e:
            raise RootFSUpdateError('Rollback failed on %s: %s' %
                                    (self.host.hostname, str(e)))

        self._verify_update_completed()


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
            self._run(' '.join(statefuldev_cmd), timeout=1200)
        except error.AutoservRunError:
            update_error = StatefulUpdateError(
                    'Failed to perform stateful update on %s' %
                    self.host.hostname)
            raise update_error


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
                lambda: (self._get_kernel_tries(active_kernel_state) == 0
                         and self._get_kernel_success(active_kernel_state)),
                exception=ChromiumOSError(),
                timeout=_KERNEL_UPDATE_TIMEOUT, sleep_interval=5)
        except ChromiumOSError:
            services_status = self._run('status system-services').stdout
            if services_status != 'system-services start/running\n':
                event = ('Chrome failed to reach login screen')
            else:
                event = ('update-engine failed to call '
                         'chromeos-setgoodkernel')
            raise ChromiumOSError(
                    'After update and reboot, %s '
                    'within %d seconds' % (event, _KERNEL_UPDATE_TIMEOUT))


    def _install_update(self, update_root=True):
        """Install the requested image on the DUT, but don't start it.

        This downloads all content needed for the requested update, and
        installs it in place on the DUT.  This does not reboot the DUT,
        so the update is merely pending when the function returns.

        @param update_root: When true, force a rootfs update; otherwise
                            update the stateful partition only.
        """
        booted_version = self.host.get_release_version()
        logging.info('Updating from version %s to %s.',
                     booted_version, self.update_version)

        # Check that Dev Server is accepting connections (from autoserv's host).
        # If we can't talk to it, the machine host probably can't either.
        auserver_host = 'http://%s' % urlparse.urlparse(self.update_url)[1]
        try:
            if not dev_server.ImageServer.devserver_healthy(auserver_host):
                raise ChromiumOSError(
                    'Update server at %s not healthy' % auserver_host)
        except Exception as e:
            logging.debug('Error happens in connection to devserver: %r', e)
            raise ChromiumOSError(
                'Update server at %s not available' % auserver_host)

        logging.info('Installing from %s to %s', self.update_url,
                     self.host.hostname)

        # Reset update state.
        self._reset_update_engine()
        self._reset_stateful_partition()

        try:
            try:
                if not update_root:
                    logging.info('Root update is skipped.')
                else:
                    self.update_image()

                self.update_stateful()
            except:
                self._revert_boot_partition()
                self._reset_stateful_partition()
                raise

            logging.info('Update complete.')
        except:
            # Collect update engine logs in the event of failure.
            if self.host.job:
                logging.info('Collecting update engine logs due to failure...')
                self.host.get_file(
                        _UPDATER_LOGS, self.host.job.sysinfo.sysinfodir,
                        preserve_perm=False)
            _list_image_dir_contents(self.update_url)
            raise
        finally:
            logging.info('Update engine log has downloaded in '
                         'sysinfo/update_engine dir. Check the lastest.')


    def _check_version(self):
        """Check the image running in DUT has the desired version.

        @returns: True if the DUT's image version matches the version that
            the autoupdater tries to update to.

        """
        booted_version = self.host.get_release_version()
        return self.update_version.endswith(booted_version)


    def _try_stateful_update(self):
        """Try to use stateful update to initialize DUT.

        When DUT is already running the same version that machine_install
        tries to install, stateful update is a much faster way to clean up
        the DUT for testing, compared to a full reimage. It is implemeted
        by calling autoupdater._run_full_update, but skipping updating root,
        as updating the kernel is time consuming and not necessary.

        @param update_url: url of the image.
        @param updater: ChromiumOSUpdater instance used to update the DUT.
        @returns: True if the DUT was updated with stateful update.

        """
        self.host.prepare_for_update()

        # TODO(jrbarnette):  Yes, I hate this re.match() test case.
        # It's better than the alternative:  see crbug.com/360944.
        image_name = url_to_image_name(self.update_url)
        release_pattern = r'^.*-release/R[0-9]+-[0-9]+\.[0-9]+\.0$'
        if not re.match(release_pattern, image_name):
            return False
        if not self._check_version():
            return False
        # Following folders should be rebuilt after stateful update.
        # A test file is used to confirm each folder gets rebuilt after
        # the stateful update.
        folders_to_check = ['/var', '/home', '/mnt/stateful_partition']
        test_file = '.test_file_to_be_deleted'
        paths = [os.path.join(folder, test_file) for folder in folders_to_check]
        self._run('touch %s' % ' '.join(paths))

        self._install_update(update_root=False)

        # Reboot to complete stateful update.
        self.host.reboot(timeout=self.host.REBOOT_TIMEOUT, wait=True)

        # After stateful update and a reboot, all of the test_files shouldn't
        # exist any more. Otherwise the stateful update is failed.
        return not any(
            self.host.path_exists(os.path.join(folder, test_file))
            for folder in folders_to_check)


    def _post_update_processing(self, expected_kernel):
        """After the DUT is updated, confirm machine_install succeeded.

        @param updater: ChromiumOSUpdater instance used to update the DUT.
        @param expected_kernel: kernel expected to be active after reboot,
            or `None` to skip rollback checking.

        """
        # Touch the lab machine file to leave a marker that
        # distinguishes this image from other test images.
        # Afterwards, we must re-run the autoreboot script because
        # it depends on the _LAB_MACHINE_FILE.
        autoreboot_cmd = ('FILE="%s" ; [ -f "$FILE" ] || '
                          '( touch "$FILE" ; start autoreboot )')
        self._run(autoreboot_cmd % _LAB_MACHINE_FILE)
        self.verify_boot_expectations(
                expected_kernel, rollback_message=
                'Build %s failed to boot on %s; system rolled back to previous '
                'build' % (self.update_version, self.host.hostname))

        logging.debug('Cleaning up old autotest directories.')
        try:
            installed_autodir = autotest.Autotest.get_installed_autodir(
                    self.host)
            self._run('rm -rf ' + installed_autodir)
        except autotest.AutodirNotFoundError:
            logging.debug('No autotest installed directory found.')


    def run_update(self, force_full_update):
        """Perform a full update of a DUT in the test lab.

        This downloads and installs the root FS and stateful partition
        content needed for the update specified in `self.host` and
        `self.update_url`.  The update is performed according to the
        requirements for provisioning a DUT for testing the requested
        build.

        @param force_full_update: When true, update the root file
            system to the new build, even if the target DUT already has
            that build installed.
        @returns A tuple of the form `(image_name, attributes)`, where
            `image_name` is the name of the image installed, and
            `attributes` is new attributes to be applied to the DUT.
        """
        logging.debug('Update URL is %s', self.update_url)

        # Report provision stats.
        server_name = dev_server.get_hostname(self.update_url)
        (metrics.Counter('chromeos/autotest/provision/install')
         .increment(fields={'devserver': server_name}))

        # Create a file to indicate if provision fails. The file will be
        # removed by any successful update.
        self._run('touch %s' % PROVISION_FAILED)

        update_complete = False
        if not force_full_update:
            try:
                # If the DUT is already running the same build, try stateful
                # update first as it's much quicker than a full re-image.
                update_complete = self._try_stateful_update()
            except Exception as e:
                logging.exception(e)

        inactive_kernel = None
        if update_complete:
            logging.info('Install complete without full update')
        else:
            logging.info('DUT requires full update.')
            self.host.reboot(timeout=self.host.REBOOT_TIMEOUT, wait=True)
            self.host.prepare_for_update()

            self._install_update()

            # Give it some time in case of IO issues.
            time.sleep(10)

            inactive_kernel = self.get_kernel_state()[1]
            next_kernel = self._get_next_kernel()
            if next_kernel != inactive_kernel:
                raise ChromiumOSError(
                        'Update failed.  The kernel for next boot is %s, '
                        'but %s was expected.' %
                        (next_kernel['name'], inactive_kernel['name']))

            # Update has returned successfully; reboot the host.
            #
            # Regarding the 'crossystem' command below: In some cases,
            # the update flow puts the TPM into a state such that it
            # fails verification.  We don't know why.  However, this
            # call papers over the problem by clearing the TPM during
            # the reboot.
            #
            # We ignore failures from 'crossystem'.  Although failure
            # here is unexpected, and could signal a bug, the point of
            # the exercise is to paper over problems; allowing this to
            # fail would defeat the purpose.
            self._run('crossystem clear_tpm_owner_request=1',
                      ignore_status=True)
            self.host.reboot(timeout=self.host.REBOOT_TIMEOUT, wait=True)

        self._post_update_processing(inactive_kernel)
        image_name = url_to_image_name(self.update_url)
        # update_url is different from devserver url needed to stage autotest
        # packages, therefore, resolve a new devserver url here.
        devserver_url = dev_server.ImageServer.resolve(
                image_name, self.host.hostname).url()
        repo_url = tools.get_package_url(devserver_url, image_name)
        return image_name, {ds_constants.JOB_REPO_URL: repo_url}
