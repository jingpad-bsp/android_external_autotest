import logging
import os
import re

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros import autoupdater
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.server.cros.update_engine import omaha_devserver
from autotest_lib.server.cros.update_engine import update_engine_test
from chromite.lib import retry_util

class autoupdate_P2P(update_engine_test.UpdateEngineTest):
    """Tests a peer to peer (P2P) autoupdate."""

    version = 1

    def setup(self):
        self._omaha_devserver = None


    def cleanup(self):
        if self._omaha_devserver is not None:
            self._omaha_devserver.stop_devserver()
        logging.info('Disabling p2p_update on hosts.')
        for host in self._hosts:
            try:
                cmd = 'update_engine_client --p2p_update=no'
                retry_util.RetryException(error.AutoservRunError, 2, host.run,
                                          cmd)
            except Exception:
                logging.info('Failed to disable P2P in cleanup.')

    def _enable_p2p_update_on_hosts(self):
        """Turn on the option to enable p2p updating on both DUTs."""
        logging.info('Enabling p2p_update on hosts.')
        for host in self._hosts:
            try:
                cmd = 'update_engine_client --p2p_update=yes'
                retry_util.RetryException(error.AutoservRunError, 2, host.run,
                                          cmd)
            except Exception:
                raise error.TestFail('Failed to enable p2p on %s' % host)

            host.run('rm /var/lib/update_engine/prefs/p2p-num-attempts',
                     ignore_status=True)
            host.reboot()


    def _get_delta_payload(self, build):
        """
        Gets the GStorage URL of the N-to-N payload to use for the update.

        @param build: build string e.g samus-release/R65-10225.0.0.

        @returns the delta payload URL.

        """
        # TODO(dhaddock): Use 'delta_payloads' artifact when crbug.com/793434
        # is fixed: stage_artifacts(build, ['delta_payloads']).
        # This will make retrieving and staging the delta payload a one line
        # operation. It will also mean we can use a lab devserver to serve
        # the payload on update requests. For now we need to find the payload
        # ourselves on GStorage.
        gs = dev_server._get_image_storage_server()
        delta_regex = 'chromeos_%s*_delta_*' % build.rpartition('/')[2]
        delta_payload_url_regex = gs + build + '/' + delta_regex
        logging.debug('Trying to find payloads at %s', delta_payload_url_regex)
        delta_payloads = utils.gs_ls(delta_payload_url_regex)
        if len(delta_payloads) < 1:
            raise error.TestFail('Could not find delta payload for %s', build)
        logging.debug('Delta payloads found: %s', delta_payloads)
        logging.info('Found delta payload for test: %s', delta_payloads[0])
        return delta_payloads[0]


    def _update_dut(self, host):
        """
        Update the first DUT normally and save the update engine logs.

        @param host: the host object for the first DUT.

        """
        logging.info('Updating first DUT with a regular update.')
        try:
            updater = autoupdater.ChromiumOSUpdater(
                self._omaha_devserver.get_update_url(), host)
            updater.update_image()
        except autoupdater.RootFSUpdateError:
            logging.exception('Failed to update the first DUT.')
            raise error.TestFail('Updating the first DUT failed. Please check '
                                 'the update_engine logs in the results dir.')
        finally:
            logging.info('Saving update engine logs to results dir.')
            host.get_file('/var/log/update_engine.log',
                          os.path.join(self.resultsdir,
                                       'update_engine.log_first_dut'))
        host.reboot()


    def _check_p2p_still_enabled(self, host):
        """
        Check that updating has not affected P2P status.

        @param host: The host that we just updated.

        """
        logging.info('Checking that p2p is still enabled after update.')
        def _is_p2p_enabled():
            p2p = host.run('update_engine_client --show_p2p_update',
                           ignore_status=True)
            if p2p.stderr is not None and 'ENABLED' in p2p.stderr:
                return True
            else:
                return False

        err = 'P2P was disabled after the first DUT was updated. This is not ' \
              'expected. Something probably went wrong with the update.'

        utils.poll_for_condition(_is_p2p_enabled,
                                 exception=error.TestFail(err))


    def _update_via_p2p(self, host):
        """
        Update the second DUT via P2P from the first DUT.

        We perform a non-interactive update and update_engine will check
        for other devices that have P2P enabled and download from them instead.

        @param host: The second DUT.

        """
        logging.info('Updating second host via p2p.')

        try:
            # Start a non-interactive update which is required for p2p.
            updater = autoupdater.ChromiumOSUpdater(
                self._omaha_devserver.get_update_url(), host, interactive=False)
            updater.update_image()
        except autoupdater.RootFSUpdateError:
            logging.exception('Failed to update the second DUT via P2P.')
            raise error.TestFail('Failed to update the second DUT. Please '
                                 'checkout update_engine logs in results dir.')
        finally:
            logging.info('Saving update engine logs to results dir.')
            host.get_file('/var/log/update_engine.log',
                          os.path.join(self.resultsdir,
                                       'update_engine.log_second_dut'))

        # Return the update_engine logs so we can check for p2p entries.
        return host.run('cat /var/log/update_engine.log').stdout


    def _check_for_p2p_entries_in_update_log(self, update_engine_log):
        """
        Ensure that the second DUT actually updated via P2P.

        We will check the update_engine log for entries that tell us that the
        update was done via P2P.

        @param update_engine_log: the update engine log for the p2p update.

        """
        logging.info('Making sure we have p2p entries in update engine log.')
        line1 = "Checking if payload is available via p2p, file_id=" \
                "cros_update_size_(.*)_hash_(.*)"
        line2 = "Lookup complete, p2p-client returned URL " \
                "'http://%s:(.*)/cros_update_size_(.*)_hash_(.*).cros_au'" % \
                self._hosts[0].ip
        line3 = "Replacing URL (.*) with local URL " \
                "http://%s:(.*)/cros_update_size_(.*)_hash_(.*).cros_au " \
                "since p2p is enabled." % self._hosts[0].ip
        errline = "Forcibly disabling use of p2p for downloading because no " \
                  "suitable peer could be found."

        if re.compile(errline).search(update_engine_log) is not None:
            raise error.TestFail('P2P update was disabled because no suitable '
                                 'peer DUT was found.')
        for line in [line1, line2, line3]:
            ue = re.compile(line)
            if ue.search(update_engine_log) is None:
                raise error.TestFail('We did not find p2p string "%s" in the '
                                     'update_engine log for the second host. '
                                     'Please check the update_engine logs in '
                                     'the results directory.' % line)


    def _get_build_from_job_repo_url(self, host):
        """
        Gets the build string from a hosts job_repo_url.

        @param host: Object representing host.

        """
        info = host.host_info_store.get()
        repo_url = info.attributes.get(host.job_repo_url_attribute, '')
        if not repo_url:
            raise error.TestFail('There was no job_repo_url for %s so we '
                                 'cant get a payload to use.' % host.hostname)
        return tools.get_devserver_build_from_package_url(repo_url)


    def _verify_hosts(self, job_repo_url):
        """
        Ensure that the hosts scheduled for the test are valid.

        @param job_repo_url: URL to work out the current build.

        """
        logging.info('Making sure hosts can ping each other.')
        result = self._hosts[1].run('ping -c5 %s' % self._hosts[0].ip,
                                    ignore_status=True)
        logging.debug('Ping status: %s', result)
        if result.exit_status != 0:
            raise error.TestFail('Devices failed to ping each other.')
        # Get the current build. e.g samus-release/R65-10200.0.0
        if job_repo_url is None:
            logging.info('Making sure hosts have the same build.')
            url, build1 = self._get_build_from_job_repo_url(self._hosts[0])
            url, build2 = self._get_build_from_job_repo_url(self._hosts[1])
            if build1 != build2:
                raise error.TestFail('The builds on the hosts did not match. '
                                     'Host one: %s, Host two: %s' % (build1,
                                                                     build2))
            return url, build1
        else:
            return tools.get_devserver_build_from_package_url(job_repo_url)


    def run_once(self, hosts, job_repo_url=None):
        self._hosts = hosts
        logging.info('Hosts for this test: %s', self._hosts)

        url, build = self._verify_hosts(job_repo_url)
        self._enable_p2p_update_on_hosts()

        # Get an N-to-N delta payload to use for the test.
        # P2P updates are very slow so we will only update with a delta payload.
        delta_payload = self._get_delta_payload(build)
        self._autotest_devserver = dev_server.ImageServer(url)
        staged_url = self._stage_payload_by_uri(delta_payload)

        # Since staging delta payloads by artifact is broken (crbug.com/793434)
        # we will need to start our own devserver to serve the delta payload
        # to update requests.
        self._omaha_devserver = omaha_devserver.OmahaDevserver(
            self._autotest_devserver.hostname, staged_url, max_updates=2)
        self._omaha_devserver.start_devserver()

        # The first device just updates normally.
        self._update_dut(self._hosts[0])
        self._check_p2p_still_enabled(self._hosts[0])

        # Update the 2nd DUT with the delta payload via P2P from the 1st DUT.
        update_engine_log = self._update_via_p2p(self._hosts[1])
        self._check_for_p2p_entries_in_update_log(update_engine_log)
