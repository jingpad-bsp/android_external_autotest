# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import autoupdater, dev_server
from autotest_lib.server import autotest, test
from autotest_lib.server.cros.dynamic_suite import tools


class platform_RebootAfterUpdate(test.test):
    """Test that updates the machine, reboots, and logs in / logs out.

    This test keeps a reboot timeout in order to keep the system boot times
    regressing in performance. For example, if Chrome takes a long time to
    shutdown / hangs, other tests have much longer timeouts (to prevent them
    from being flaky) while this test targets these hangs. Note, this test only
    has smaller timeouts for boot, not for login/logout. Also, these timeouts
    are still fairly conservative and are only meant to catch large regressions
    or hangs, not small regressions.

    """
    version = 1

    _REBOOT_ERROR_MESSAGE = (
            'System failed to restart within the timeout after '
            '%(reason)s. This failure indicates that the system after '
            'receiving a reboot request and restarting did not '
            'reconnect via ssh within the timeout. Actual time %(actual)d '
            'seconds vs expected time: %(expected)d seconds')

    # Timeouts specific to this test. These should be as low as possible.

    # Total amount of time to wait for a reboot to return.
    _REBOOT_TIMEOUT = 60


    @classmethod
    def reboot_with_timeout(cls, host, reason):
        """Reboots the device and checks to see if it completed within desired.

        @param host: Autotest host object to reboot.
        @param reason: string representing why we are rebooting e.g. autoupdate.

        Raises:
            error.TestFail: If it takes too long to reboot.
        """
        start_time = time.time()
        host.reboot()
        reboot_duration = time.time() - start_time
        if reboot_duration > cls._REBOOT_TIMEOUT:
            raise error.TestFail(
                cls._REBOOT_ERROR_MESSAGE % dict(
                        reason=reason, actual=reboot_duration,
                        expected=cls._REBOOT_TIMEOUT))


    def run_once(self, host, job_repo_url=None):
        """Runs the test.

        @param host: a host object representing the DUT
        @param job_repo_url: URL to get the image.

        @raise error.TestError if anything went wrong with setting up the test;
               error.TestFail if any part of the test has failed.

        """
        # Get the job_repo_url -- if not present, attempt to use the one
        # specified in the host attributes for the host.
        if not job_repo_url:
            try:
                job_repo_url = host.lookup_job_repo_url()
            except KeyError:
                logging.fatal('Could not lookup job_repo_url from afe.')

            if not job_repo_url:
                raise error.TestError(
                        'Test could not be run. Missing the url with which to '
                        're-image the device!')

        # Get the devserver url and build (image) from the repo url e.g.
        # 'http://mydevserver:8080', 'x86-alex-release/R27-123.0.0'
        ds, build = tools.get_devserver_build_from_package_url(job_repo_url)
        devserver = dev_server.ImageServer(ds)

        # We only need to update stateful to do this test.
        updater = autoupdater.ChromiumOSUpdater(
                devserver.get_update_url(build), host=host)
        updater.update_stateful(clobber=True)

        logging.info('Rebooting after performing update.')
        self.reboot_with_timeout(host, 'update')

        # TODO(sosa): Ideally we would be able to just use
        # autotest.run_static_method to login/logout, however, this
        # functionality is currently nested deep into the test logic. Once
        # telemetry has replaced pyauto login and has been librarized, we
        # should switch to using that code and not have to rely on running a
        # client test to do what we want.
        logging.info('Running sanity desktop login to see that we can '
                     'login and logout after performing an update.')
        client_at = autotest.Autotest(host)
        self.job.set_state('client_success', False)
        client_at.run_test('login_LoginSuccess')
        if not self.job.get_state('client_success'):
            raise error.TestFail(
                    'Failed to login successfully after an update.')

        logging.info('Rebooting the DUT after first login/logout.')
        self.reboot_with_timeout(host, 'first login')
