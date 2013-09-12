# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import logging
import time
import os
import urllib2
import urlparse

from autotest_lib.client.bin import utils as client_utils
from autotest_lib.client.common_lib import error, global_config
from autotest_lib.client.common_lib.cros import autoupdater, dev_server
from autotest_lib.server import hosts, test
from autotest_lib.server.cros.dynamic_suite import tools


def _wait(secs, desc=None):
    """Emits a log message and sleeps for a given number of seconds."""
    msg = 'waiting %s seconds' % secs
    if desc:
        msg += ' (%s)' % desc
    logging.info(msg)
    time.sleep(secs)


class ExpectedUpdateEvent(object):
    """Defines an expected event in a host update process."""

    # Omaha event types/results, from update_engine/omaha_request_action.h
    # These are stored in dict form in order to easily print out the keys.
    EVENT_TYPE_DICT = {
            '0':'unknown', '1':'download_complete', '2':'install_complete',
            '3':'update_complete', '13':'download_started',
            '14':'download_finished'}

    EVENT_RESULT_DICT = {
            '0': 'error', '1':'success', '2':'success_reboot',
            '9':'update_deferred'}

    VALID_TYPES = set(EVENT_TYPE_DICT.values())
    VALID_RESULTS = set(EVENT_RESULT_DICT.values())

    def __init__(self, event_type=None, event_result=None, version=None,
                 previous_version=None):
        if event_type and event_type not in self.VALID_TYPES:
            raise ValueError('event_type %s is not valid.' % event_type)

        if event_result and event_result not in self.VALID_RESULTS:
            raise ValueError('event_result %s is not valid.' % event_result)

        self._expected_attrs = {
            'event_type': event_type,
            'event_result': event_result,
            'version': version,
            'previous_version': previous_version,
        }


    def __str__(self):
        return ' '.join(['%s=%s' % (attr_name, attr_val or 'any')
                         for attr_name, attr_val
                         in self._expected_attrs.iteritems()])


    def verify(self, actual_event):
        """Verify the attributes of an actual event.

        @param actual_event: a dictionary containing event attributes

        @return True if all attributes as expected, False otherwise.

        """
        return all([self._verify_attr(attr_name, expected_attr_val,
                                      actual_event.get(attr_name))
                    for attr_name, expected_attr_val
                    in self._expected_attrs.iteritems() if expected_attr_val])


    def _verify_attr(self, attr_name, expected_attr_val, actual_attr_val):
        """Verifies that an actual log event attributes matches expected on.

        @param attr_name: name of the attribute to verify
        @param expected_attr_val: expected attribute value
        @param actual_attr_val: actual attribute value

        @return True if actual value is present and matches, False otherwise.

        """
        # None values are assumed to be missing and non-matching.
        if not actual_attr_val:
            logging.error('No value found for %s -- expected %s', attr_name,
                          expected_attr_val)
            return False

        helper_dict = None
        if attr_name == 'event_type':
            helper_dict = self.EVENT_TYPE_DICT
        elif attr_name == 'event_result':
            helper_dict = self.EVENT_RESULT_DICT

        # Convert to strings for easy matching.
        expected_attr_val = str(expected_attr_val)
        actual_attr_val = str(actual_attr_val)

        # For event_type|result use the more helpful string form.
        # If we get a code that is not in our known codes, use
        # "Unknown value $value" instead.
        if helper_dict:
            actual_attr_val = helper_dict.get(
                    actual_attr_val, 'Unknown value: %s' % actual_attr_val)

        if not actual_attr_val == expected_attr_val:
            if ('version' in attr_name and
                expected_attr_val in actual_attr_val):
                # We allow for version like 2940.0.0 in 2940.0.0-a1 to allow
                # this test to pass for developer images and non-release images.
                logging.info("Expected version %s in %s but doesn't "
                             "match exactly", expected_attr_val,
                             actual_attr_val)
                return True

            logging.error(
                    'actual %s (%s) not as expected (%s)',
                    attr_name, actual_attr_val, expected_attr_val)
            return False

        return True


class ExpectedUpdateEventChain(object):
    """Defines a chain of expected update events."""
    def __init__(self, *expected_event_chain_args):
        """Initialize the chain object.

        @param expected_event_chain_args: list of tuples arguments, each
               containing a timeout (in seconds) and an ExpectedUpdateEvent
               object.

        """
        self._expected_event_chain = expected_event_chain_args


    def _format_event_with_timeout(self, timeout, expected_event):
        return ('%s %s' %
                (expected_event,
                 ('within %s seconds' % timeout) if timeout
                 else 'indefinitely'))


    def __str__(self):
        return ('[%s]' %
                ', '.join(
                    [self._format_event_with_timeout(timeout, expected_event)
                     for timeout, expected_event
                     in self._expected_event_chain]))


    def __repr__(self):
        return str(self._expected_event_chain)


    def verify(self, get_next_event):
        """Verifies that an actual stream of events complies.

        @param get_next_event: a function returning the next event

        @return True if chain was satisfied, False otherwise.

        """
        for timeout, expected_event in self._expected_event_chain:
            logging.info(
                    'expecting %s',
                    self._format_event_with_timeout(timeout, expected_event))
            if not self._verify_event_with_timeout(
                    timeout, expected_event, get_next_event):
                return False
        return True


    def _verify_event_with_timeout(self, timeout, expected_event,
                                   get_next_event):
        """Verify an expected event occurs within a given timeout.

        @param timeout: specified in seconds
        @param expected_event: an expected event specification
        @param get_next_event: function returning the next event in a stream

        @return True if event complies, False otherwise.

        """
        base_timestamp = curr_timestamp = time.time()
        expired_timestamp = base_timestamp + timeout
        while curr_timestamp <= expired_timestamp:
            new_event = get_next_event()
            if new_event:
                logging.info('event received after %s seconds',
                             curr_timestamp - base_timestamp)
                return expected_event.verify(new_event)

            # No new events, sleep for one second only (so we don't miss
            # events at the end of the allotted timeout).
            time.sleep(1)
            curr_timestamp = time.time()

        logging.error('timeout expired')
        return False


class UpdateEventLogVerifier(object):
    """Verifies update event chains on a devserver update log."""
    def __init__(self, event_log_url, url_request_timeout=None):
        self._event_log_url = event_log_url
        self._url_request_timeout = url_request_timeout
        self._event_log = []
        self._num_consumed_events = 0


    def verify_expected_event_chain(self, expected_event_chain):
        """Verify a given event chain.

        @param expected_event_chain: instance of expected event chain.
        """
        return expected_event_chain.verify(self._get_next_log_event)


    def _get_next_log_event(self):
        """Returns the next event in an event log.

        Uses the URL handed to it during initialization to obtain the host log
        from a devserver. If new events are encountered, the first of them is
        consumed and returned.

        @return The next new event in the host log, as reported by devserver;
                None if no such event was found or an error occurred.

        """
        # (Re)read event log from devserver, if necessary.
        if len(self._event_log) <= self._num_consumed_events:
            try:
                if self._url_request_timeout:
                    conn = urllib2.urlopen(self._event_log_url,
                                           timeout=self._url_request_timeout)
                else:
                    conn = urllib2.urlopen(self._event_log_url)
            except urllib2.URLError, e:
                logging.warning('urlopen failed: %s', e)
                return None

            event_log_resp = conn.read()
            conn.close()
            self._event_log = json.loads(event_log_resp)

        # Return next new event, if one is found.
        if len(self._event_log) > self._num_consumed_events:
            new_event = self._event_log[self._num_consumed_events]
            self._num_consumed_events += 1
            logging.info('consumed new event: %s', new_event)
            return new_event


class OmahaDevserverFailedToStart(error.TestError):
    """Raised when a omaha devserver fails to start."""


class OmahaDevserver(object):
    """Spawns a test-private devserver instance."""
    # How long to wait for a devserver to start.
    _WAIT_FOR_DEVSERVER_STARTED_SECONDS = 15

    # How long to sleep between checks to see if a devserver is up.
    _WAIT_SLEEP_INTERVAL = 1

    # If a previous devserver exists, how long to wait in seconds before
    # attempting to reconnect.
    _TIME_TO_LET_PORT_FREE = 15

    # How many times to attempt to start a devserver.
    _NUM_DEVSERVER_ATTEMPTS = 5


    def __init__(self, omaha_host, devserver_dir, dut_ip_addr,
                 update_payload_lorry_url):
        """Starts a private devserver instance, operating at Omaha capacity.

        @param omaha_host: host address where the devserver is spawned.
        @param devserver_dir: path to the devserver source directory
        @param dut_ip_addr: the IP address of the client DUT, used for deriving
               a unique port number.
        @param update_payload_lorry_url: URL to provision for update requests.

        """
        if not update_payload_lorry_url:
            raise error.TestError('missing update payload url')

        self._omaha_host = omaha_host
        self._omaha_port = self._get_unique_port(dut_ip_addr)
        self._devserver_dir = devserver_dir
        self._update_payload_lorry_url = update_payload_lorry_url

        self._devserver_ssh = hosts.SSHHost(self._omaha_host,
                                            user=os.environ['USER'])
        self._devserver_output = '/tmp/devserver.%s' % self._omaha_port
        self._devserver_pid = None


    def _wait_for_devserver_to_start(self):
        """Waits until the devserver starts within the time limit.

        Raises:
            OmahaDevserverFailedToStart: If the time limit is reached and we
                                         cannot connect to the devserver.
        """
        logging.warning('Waiting for devserver to start up.')
        timeout = self._WAIT_FOR_DEVSERVER_STARTED_SECONDS
        netloc = self.get_netloc()
        current_time = time.time()
        deadline = current_time + timeout
        while(current_time < deadline):
            if dev_server.DevServer.devserver_healthy('http://%s' % netloc,
                                                      timeout_min=0.1):
                return

            # TODO(milleral): Refactor once crbug.com/221626 is resolved.
            time.sleep(self._WAIT_SLEEP_INTERVAL)
            current_time = time.time()
        else:
            raise OmahaDevserverFailedToStart(
                    'The test failed to establish a connection to the omaha '
                    'devserver it set up on port %d. Check the dumped '
                    'devserver logs for more information.' % self._omaha_port)


    def start_devserver(self):
        """Starts the devserver and confirms it is up.

        Stores the remote pid in self._devserver_pid and raises an exception
        if the devserver failed to start.

        Raises:
            OmahaDevserverFailedToStart: If the time limit is reached and we
                                         cannot connect to the devserver.
        """
        update_payload_url_base, update_payload_path = self._split_url(
                self._update_payload_lorry_url)
        # Invoke the Omaha/devserver on the remote server.
        cmdlist = [
                '%s/devserver.py' % self._devserver_dir,
                '--payload=%s' % update_payload_path,
                '--port=%d' % self._omaha_port,
                '--remote_payload',
                '--urlbase=%s' % update_payload_url_base,
                '--max_updates=1',
                '--host_log',
        ]
        remote_cmd = '( %s ) </dev/null >%s 2>&1 & echo $!' % (
                    ' '.join(cmdlist), self._devserver_output)

        # Devserver may have some trouble re-using the port if previously
        # created so create in a loop with a max number of attempts.
        for i in range(self._NUM_DEVSERVER_ATTEMPTS):
            # In the remote case that a previous devserver is still running,
            # kill it.
            devserver_pid = self._remote_devserver_pid()
            if devserver_pid:
                logging.warning('Previous devserver still running. Killing.')
                self._kill_devserver_pid(devserver_pid)
                self._devserver_ssh.run('rm -f %s' % self._devserver_output,
                                        ignore_status=True)
                time.sleep(self._TIME_TO_LET_PORT_FREE)

            logging.info('Starting devserver with %r', remote_cmd)
            self._devserver_pid = self._devserver_ssh.run_output(remote_cmd)
            try:
                self._wait_for_devserver_to_start()
                return
            except OmahaDevserverFailedToStart:
                if i + 1 < self._NUM_DEVSERVER_ATTEMPTS:
                    logging.error('Devserver failed to start, re-attempting.')
                else:
                    self.dump_devserver_log()
                    raise


    def _kill_devserver_pid(self, pid):
        """Kills devserver with given pid and verifies devserver is down.

        @param pid: The pid of the devserver to kill.

        @raise client_utils.TimeoutError if we are unable to kill the devserver
               within the default timeouts (11 seconds).
        """
        def _devserver_down():
            return self._remote_devserver_pid() == None

        self._devserver_ssh.run('kill %s' % pid)
        try:
            client_utils.poll_for_condition(_devserver_down,
                                            sleep_interval=1)
            return
        except client_utils.TimeoutError:
            logging.warning('Could not gracefully shut down devserver.')

        self._devserver_ssh.run('kill -9 %s' % pid)
        client_utils.poll_for_condition(_devserver_down, timeout=1)


    def _remote_devserver_pid(self):
        """If a devserver is running on our port, return its pid."""
        # fuser returns pid in its stdout if found.
        result = self._devserver_ssh.run('fuser -n tcp %d' % self._omaha_port,
                                         ignore_status=True)
        if result.exit_status == 0:
            return result.stdout.strip()


    def get_netloc(self):
        """Returns the netloc (host:port) of the devserver."""
        if not self._devserver_pid:
            raise error.TestError('no running omaha/devserver')


        return '%s:%s' % (self._omaha_host, self._omaha_port)


    def get_update_url(self):
        """Returns the update_url you can use to update via this server."""
        return urlparse.urlunsplit(('http', self.get_netloc(), '/update',
                                    '', ''))


    def dump_devserver_log(self, logging_level=logging.ERROR):
        """Dump the devserver log to the autotest log.

        @param logging_level: logging level (from logging) to log the output.
        """
        if self._devserver_pid:
            logging.log(logging_level, self._devserver_ssh.run_output(
                    'cat %s' % self._devserver_output))


    @staticmethod
    def _split_url(url):
        """Splits a URL into the URL base and path."""
        split_url = urlparse.urlsplit(url)
        url_base = urlparse.urlunsplit(
                (split_url.scheme, split_url.netloc, '', '', ''))
        url_path = split_url.path
        return url_base, url_path.lstrip('/')


    @staticmethod
    def _get_unique_port(dut_ip_addr):
        """Compute a unique IP port based on the DUT's IP address.

        We need a mapping that can be mirrored by a DUT running an official
        image, based only on the DUT's own state. Here, we simply take the two
        least significant bytes in the DUT's IPv4 address and bitwise-OR them
        with 0xc0000, resulting in a 16-bit IP port within the
        private/unallocated range. Using the least significant bytes of the IP
        address guarantees (sort of) that we'll have a unique mapping in a
        small lab setting.

        """
        ip_addr_bytes = [int(byte_str) for byte_str in dut_ip_addr.split('.')]
        return (((ip_addr_bytes[2] << 8) | ip_addr_bytes[3] | 0x8000) & ~0x4000)


    def kill(self):
        """Kill private devserver, wait for it to die."""
        if not self._devserver_pid:
            raise error.TestError('no running omaha/devserver')

        logging.info('killing omaha/devserver')
        logging.debug('Final devserver log before killing')
        self._kill_devserver_pid(self._devserver_pid)
        self.dump_devserver_log(logging.DEBUG)
        self._devserver_ssh.run('rm -f %s' % self._devserver_output)


class autoupdate_EndToEndTest(test.test):
    """Complete update test between two Chrome OS releases.

    Performs an end-to-end test of updating a ChromeOS device from one version
    to another. This script requires a running (possibly remote) servod
    instance connected to an actual servo board, which controls the DUT. It
    also assumes that a corresponding target (update) image was staged for
    download on the central Lorry/devserver.

    The test performs the following steps:

      0. Stages the source image and target update payload on the central
         Lorry/devserver.
      1. Spawns a private Omaha/devserver instance, configured to return the
         target (update) image URL in response for an update check.
      2. Connects to servod.
         a. Resets the DUT to a known initial state.
         b. Installs a source image on the DUT via recovery.
      3. Reboots the DUT with the new image.
      4. Triggers an update check at the DUT.
      5. Watches as the DUT obtains an update and applies it.
      6. Repeats 3-5, ensuring that the next update check shows the new image
         version.

    """
    version = 1

    # Timeout periods, given in seconds.
    _WAIT_AFTER_SHUTDOWN_SECONDS = 10
    _WAIT_AFTER_UPDATE_SECONDS = 20
    _WAIT_FOR_USB_INSTALL_SECONDS = 4 * 60
    _WAIT_FOR_MP_RECOVERY_SECONDS = 8 * 60
    _WAIT_FOR_INITIAL_UPDATE_CHECK_SECONDS = 12 * 60
    # TODO(sosa): Investigate why this needs to be so long (this used to be
    # 120 and regressed).
    _WAIT_FOR_DOWNLOAD_STARTED_SECONDS = 4 * 60
    _WAIT_FOR_DOWNLOAD_COMPLETED_SECONDS = 10 * 60
    _WAIT_FOR_UPDATE_COMPLETED_SECONDS = 4 * 60
    _WAIT_FOR_UPDATE_CHECK_AFTER_REBOOT_SECONDS = 15 * 60
    _DEVSERVER_HOSTLOG_REQUEST_TIMEOUT_SECONDS = 30

    # Named tuple containing urls for staged urls needed for test.
    # source_url: url to find the update payload for the source image.
    # source_stateful_url: url to find the stateful payload for the source
    #                      image.
    # target_url: url to find the update payload for the target image.
    # target_stateful_url: url to find the stateful payload for the target
    #                      image.
    _STAGED_URLS = collections.namedtuple(
            'StagedUrls',
            ['source_url', 'source_stateful_url', 'target_url',
             'target_stateful_url'])


    def _servo_dut_power_up(self):
        """Powers up the DUT, optionally simulating a Ctrl-D key press."""
        self._host.servo.power_short_press()
        if self._dev_mode:
            self._host.servo.pass_devmode()


    def _servo_dut_reboot(self, disconnect_usbkey=False):
        """Reboots a DUT.

        @param disconnect_usbkey: detach USB flash device from the DUT before
               powering it back up; this is useful when (for example) a USB
               booted device need not see the attached USB key after the
               reboot.

        @raise error.TestFail if DUT fails to reboot.

        """
        logging.info('rebooting dut')
        self._host.servo.power_long_press()
        _wait(self._WAIT_AFTER_SHUTDOWN_SECONDS, 'after shutdown')
        if disconnect_usbkey:
            self._host.servo.switch_usbkey('host')

        self._servo_dut_power_up()
        if self._use_test_image:
            if not self._host.wait_up(timeout=self._host.BOOT_TIMEOUT):
                raise error.TestFail(
                        'dut %s failed to boot after %d secs' %
                        (self._host.ip, self._host.BOOT_TIMEOUT))
        else:
          # TODO(garnold) chromium-os:33766: implement waiting for MP-signed
          # images; ideas include waiting for a ping reply, or using a GPIO
          # signal.
          pass


    def _install_mp_image(self, lorry_image_url):
        """Installs an MP-signed recovery image on a DUT.

        @param lorry_image_url: URL of the image on a Lorry/devserver
        """
        # Flash DUT with source image version, using recovery.
        logging.info('installing source mp-signed image via recovery: %s',
                     lorry_image_url)
        self._host.servo.install_recovery_image(
                lorry_image_url,
                wait_timeout=self._WAIT_FOR_MP_RECOVERY_SECONDS)

        # Reboot the DUT after installation.
        self._servo_dut_reboot(disconnect_usbkey=True)


    def _install_test_image_with_servo(self, lorry_image_url):
        """Installs a test image on a DUT, booted via recovery.

        @param lorry_image_url: URL of the image on a Lorry/devserver
        @param is_dev_nmode: whether or not the DUT is in dev mode

        @raise error.TestFail if DUT cannot boot the test image from USB;
               AutotestHostRunError if failed to run the install command on the
               DUT.

        """
        logging.info('installing source test image via recovery: %s',
                     lorry_image_url)
        self._host.servo.install_recovery_image(lorry_image_url)
        logging.info('waiting for image to boot')
        if not self._host.wait_up(timeout=self._host.USB_BOOT_TIMEOUT):
          raise error.TestFail(
              'dut %s boot from usb timed out after %d secs' %
              (self._host, self._host.USB_BOOT_TIMEOUT))
        logging.info('installing new image onto ssd')
        try:
            cmd_result = self._host.run(
                    'chromeos-install --yes',
                    timeout=self._WAIT_FOR_USB_INSTALL_SECONDS,
                    stdout_tee=None, stderr_tee=None)
        except error.AutotestHostRunError:
            # Dump stdout (with stderr) to the error log.
            logging.error('command failed, stderr:\n' + cmd_result.stderr)
            raise

        # Reboot the DUT after installation.
        self._servo_dut_reboot(disconnect_usbkey=True)


    def _trigger_test_update(self, omaha_devserver):
        """Trigger an update check on a test image.

        Uses update_engine_client via SSH. This is an async call, hence a very
        short timeout.

        @param omaha_devserver: Instance of OmahaDevserver that will serve the
                                update.
        @raise RootFSUpdateError if anything went wrong.

        """
        updater = autoupdater.ChromiumOSUpdater(
                omaha_devserver.get_update_url(), host=self._host)
        updater.trigger_update()


    def _get_rootdev(self):
        """Returns the partition device containing the rootfs on a host.

        @return The rootfs partition device (string).

        @raise AutotestHostRunError if command failed to run on host.

        """
        # This command should return immediately, hence the short timeout.
        return self._host.run('rootdev -s', timeout=10).stdout.strip()


    def _stage_image(self, lorry_devserver, image_uri):
        """Stage a Chrome OS image on Lorry/devserver.

        @param lorry_devserver: instance of client.common_lib.dev_server to use
                                to reach the devserver instance for this build.
        @param image_uri: The uri of the image.
        @return URL of the staged image on the server.

        @raise error.TestError if there's a problem with staging.

        """
        if self._use_test_image:
            # For this call, we just need the URL path up to the image.zip file
            # (exclusive).
            image_uri_path = urlparse.urlsplit(image_uri).path.partition(
                    'image.zip')[0].strip('/')
            try:
                lorry_devserver.stage_artifacts(image_uri_path, ['test_image'])
                return lorry_devserver.get_test_image_url(image_uri_path)
            except dev_server.DevServerException, e:
                raise error.TestError(
                        'failed to stage source test image: %s' % e)
        else:
            # TODO(garnold) chromium-os:33766: implement staging of MP-signed
            # images.
            raise NotImplementedError()


    def _stage_payload(self, lorry_devserver, payload_uri=None,
                       devserver_label=None, filename=None):
        """Stage the given payload onto the devserver.

        Works for either a stateful or full/delta test payload. Expects the
        gs_path or a combo of devserver_label + filename.

        @param lorry_devserver: instance of client.common_lib.dev_server to use
                                to reach the devserver instance for this build.
        @param payload_uri: The full uri of the payload
        @param devserver_label: The build name e.g. x86-mario-release/<version>.
                                If set, assumes default gs archive bucket and
                                requires filename to be specified.
        @param filename: In conjunction with devserver_label, if just specifying
                         the devserver label name, this is which file are you
                         downloading.

        @return URL of the staged payload on the server.

        @raise error.TestError if there's a problem with staging.

        """
        if not ((devserver_label and filename) or payload_uri):
            raise error.TestError(
                    'failed to stage payload: insufficent arguments.')

        payload_archive_url = None
        if not (devserver_label and filename):
            payload_archive_url, _, filename = payload_uri.rpartition('/')
            devserver_label = urlparse.urlsplit(
                    payload_archive_url).path.strip('/')
        try:
            lorry_devserver.stage_artifacts(
                    image=devserver_label, artifacts=None, files=[filename],
                    archive_url=payload_archive_url)
            return lorry_devserver.get_staged_file_url(filename,
                                                       devserver_label)
        except dev_server.DevServerException, e:
            raise error.TestError('failed to stage payload: %s' % e)


    def _payload_to_update_url(self, payload_url):
        """Given a update or stateful payload url, returns the update url."""
        # We want to transform it to the correct omaha url which is
        # <hostname>/update/...LABEL.
        base_url = payload_url.rpartition('/')[0]
        return base_url.replace('/static/', '/update/')


    def _payload_to_stateful_url(self, payload_url):
        """Given a payload url, returns the stateful url."""
        base_url = payload_url.rpartition('/')[0]
        return '/'.join([base_url, 'stateful.tgz'])


    def update_via_test_payloads(self, omaha_host, payload_url, stateful_url,
                                 clobber):
      """Given the following update and stateful urls, update the DUT.

      Only updates the rootfs/stateful if the respective url is provided.

      @param omaha_host: If updating rootfs, redirect updates through this
                         host. Should be None iff payload_url is None.
      @param payload_url: If set, the specified url to find the update payload.
      @param stateful_url: If set, the specified url to find the stateful
                           payload.
      @param clobber: If True, do a clean install of stateful.
      """
      # We create a OmahaDevserver to redirect blah.bin to update/. This allows
      # us to use any payload filename to serve an update.
      temp_devserver = None
      try:
          if payload_url:
              temp_devserver = OmahaDevserver(
                      omaha_host, self._devserver_dir, self._host.ip,
                      payload_url)
              temp_devserver.start_devserver()
              payload_url = temp_devserver.get_update_url()

          stateful_url = self._payload_to_update_url(stateful_url)

          for (url, is_stateful) in (payload_url, False), (stateful_url, True):
              if not url:
                  continue

              updater = autoupdater.ChromiumOSUpdater(url, host=self._host)
              if not is_stateful:
                  updater.update_rootfs()
              else:
                  updater.update_stateful(clobber=clobber)
      finally:
          if temp_devserver:
              temp_devserver.kill()


    def install_source_version(self, omaha_host, image_url, stateful_url):
        """Prepare the specified host with the image given by the urls.

        @param omaha_host: If updating rootfs, redirect updates through this
                           host. Should be None iff image_url is None.
        @param image_url: If set, the specified url to find the source image
                          or full payload for the source image.
        @param stateful_url: If set, the specified url to find the stateful
                             payload.
        """
        if self._use_servo:
            # Install source image (test vs MP).
            if self._use_test_image:
                self._install_test_image_with_servo(image_url)
            else:
                self._install_mp_image(image_url)

        else:
            try:
                # Reboot to get us into a clean state.
                self._host.reboot()
                # Since we are installing the source image of the test, clobber
                # stateful.
                self.update_via_test_payloads(omaha_host, image_url,
                                              stateful_url, clobber=True)
                self._host.reboot()
            except error.AutoservRunError:
                logging.fatal('Error re-imaging the machine with the source '
                              'image %s', image_url)
                raise error.TestError(
                        'Could not update to pre-conditions of test. This is '
                        'most likely a problem with the autotest lab and not '
                        'autoupdate.')


    def stage_artifacts_onto_devserver(self, lorry_devserver, test_conf):
        """Stages artifacts that will be used by the test onto the devserver.

        @param lorry_devserver: instance of client.common_lib.dev_server to use
                                to reach the devserver instance for this build.
        @param test_conf: a dictionary containing test configuration values

        @return a _STAGED_URLS tuple containing the staged urls.
        """
        logging.info('staging images onto lorry/devserver (%s)',
                     lorry_devserver.url())

        source_url = None
        if self._use_servo:
            source_url = self._stage_image(
                    lorry_devserver, test_conf['source_image_uri'])
            # Test image already has stateful payload.
            source_stateful_url = None
            logging.info('test image for source image staged at %s', source_url)
        else:
            source_url = self._stage_payload(
                    lorry_devserver, test_conf['source_image_uri'])

            # Tests may have their source artifacts in a different location than
            # their payloads. If so, this is set. If not set, use the same path
            # to the source image minus the name of the payload.
            source_archive_uri = test_conf.get('source_archive_uri')
            if not source_archive_uri:
                source_archive_uri = self._payload_to_stateful_url(
                        test_conf['source_image_uri'])
            else:
                source_archive_uri = '/'.join([source_archive_uri,
                                               'stateful.tgz'])

            source_stateful_url = self._stage_payload(lorry_devserver,
                                                      source_archive_uri)

        target_url = self._stage_payload(
                lorry_devserver, test_conf['target_payload_uri'])
        if self._job_repo_url:
            _, devserver_label = tools.get_devserver_build_from_package_url(
                    self._job_repo_url)
            target_stateful_url = self._stage_payload(
                    lorry_devserver, None, devserver_label, 'stateful.tgz')
        else:
            target_archive_uri = self._payload_to_stateful_url(
                    test_conf['source_image_uri'])
            target_stateful_url = self._stage_payload(
                    lorry_devserver, target_archive_uri)

        # Log all the urls.
        logging.info('%s payload for update test staged at %s',
                     test_conf['update_type'], target_url)
        logging.info('stateful payload for target image staged at %s',
                     target_stateful_url)
        if source_url:
            logging.info('full payload for source image staged at %s',
                         source_url)
            logging.info('stateful payload for source image staged at %s',
                         source_stateful_url)

        return self._STAGED_URLS(source_url, source_stateful_url,
                                 target_url, target_stateful_url)


    def initialize(self):
        """Sets up variables that will be used by test."""
        self._host = None
        self._use_servo = False
        self._dev_mode = False
        self._omaha_devserver = None

        self._use_test_image = True
        self._job_repo_url = None
        self._devserver_dir = global_config.global_config.get_config_value(
                'CROS', 'devserver_dir', default=None)
        if self._devserver_dir is None:
            raise error.TestError(
                    'path to devserver source tree not provided; please define '
                    'devserver_dir under [CROS] in your shadow_config.ini')


    def cleanup(self):
        """Kill the omaha devserver if it's still around."""
        if self._omaha_devserver:
            self._omaha_devserver.kill()

        self._omaha_devserver = None


    def _verify_preconditions(self):
        """Validate input args make sense."""
        if self._use_servo and not self._host.servo:
            raise error.AutotestError('Servo use specified but no servo '
                                      'attached to host object.')

        if not self._use_test_image and not self._use_servo:
            raise error.TestError("Can't install mp image without servo.")


    def _log_error_and_fail(self, message):
        """Dumps relevant AU error log, and fails with message.

        Raises:
            error.TestFail: with message given -- always.
        """
        if not self._use_servo:
            logging.error('Test failed -- dumping snippet of update_engine log')
            error_log = self._host.run_output(
                    'tail -n 40 /var/log/update_engine.log')
            logging.error(error_log)

        raise error.TestFail(message)


    def run_once(self, host, test_conf, use_servo):
        """Performs a complete auto update test.

        @param host: a host object representing the DUT
        @param test_conf: a dictionary containing test configuration values
        @param use_servo: True whether we should use servo.

        @raise error.TestError if anything went wrong with setting up the test;
               error.TestFail if any part of the test has failed.

        """
        # Attempt to get the job_repo_url to find the stateful payload for the
        # target image.
        try:
            self._job_repo_url = host.lookup_job_repo_url()
        except KeyError:
            logging.warning('Job Repo URL not found. Assuming stateful '
                            'payload can be found along with the target update')

        self._host = host
        self._use_test_image = test_conf.get('image_type') != 'mp'
        self._use_servo = use_servo
        if self._use_servo:
            self._dev_mode = self._host.servo.get('dev_mode') == 'on'

        # Verify that our arguments are sane.
        self._verify_preconditions()

        # Stage source images and update payloads on lorry/devserver. We use
        # the payload URI as argument for the lab's devserver load-balancing
        # mechanism.
        lorry_devserver = dev_server.ImageServer.resolve(
                test_conf['target_payload_uri'])
        omaha_host = urlparse.urlparse(lorry_devserver.url()).hostname

        # Ensure all the artifacts we'll need for this test and grab the urls
        # on the devserver they are staged onto.
        staged_urls = self.stage_artifacts_onto_devserver(
                lorry_devserver, test_conf)

        # Install the source version onto the DUT.
        self.install_source_version(omaha_host, staged_urls.source_url,
                                    staged_urls.source_stateful_url)

        # On test images, record the active root partition.
        source_rootfs_partition = None
        if self._use_test_image:
            source_rootfs_partition = self._get_rootdev()
            logging.info('source image rootfs partition: %s',
                         source_rootfs_partition)

        self._omaha_devserver = OmahaDevserver(
                omaha_host, self._devserver_dir, self._host.ip,
                staged_urls.target_url)

        self._omaha_devserver.start_devserver()

        # Trigger an update.
        if self._use_test_image:
            self._trigger_test_update(self._omaha_devserver)
        else:
            # TODO(garnold) chromium-os:33766: use GPIOs to trigger an
            # update.
            pass

        # Track update progress.
        omaha_netloc = self._omaha_devserver.get_netloc()
        omaha_hostlog_url = urlparse.urlunsplit(
                ['http', omaha_netloc, '/api/hostlog',
                 'ip=' + self._host.ip, ''])
        logging.info('polling update progress from omaha/devserver: %s',
                     omaha_hostlog_url)
        log_verifier = UpdateEventLogVerifier(
                omaha_hostlog_url,
                self._DEVSERVER_HOSTLOG_REQUEST_TIMEOUT_SECONDS)

        # Verify chain of events in a successful update process.
        chain = ExpectedUpdateEventChain(
                (self._WAIT_FOR_INITIAL_UPDATE_CHECK_SECONDS,
                 ExpectedUpdateEvent(
                     version=test_conf['source_release'])),
                (self._WAIT_FOR_DOWNLOAD_STARTED_SECONDS,
                 ExpectedUpdateEvent(
                     event_type='download_started',
                     event_result='success',
                     version=test_conf['source_release'])),
                (self._WAIT_FOR_DOWNLOAD_COMPLETED_SECONDS,
                 ExpectedUpdateEvent(
                     event_type='download_finished',
                     event_result='success',
                     version=test_conf['source_release'])),
                (self._WAIT_FOR_UPDATE_COMPLETED_SECONDS,
                 ExpectedUpdateEvent(
                     event_type='update_complete',
                     event_result='success',
                     version=test_conf['source_release'])))

        if not log_verifier.verify_expected_event_chain(chain):
            self._log_error_and_fail(
                    'update failed to apply, see logs for the culprit.')

        # Wait after an update completion (safety margin).
        _wait(self._WAIT_AFTER_UPDATE_SECONDS, 'after update completion')

        # Reboot the DUT after the update.
        if use_servo:
            self._servo_dut_reboot()
        else:
            # Only update the stateful partition since the test has updated the
            # rootfs.
            self.update_via_test_payloads(
                    None, None, staged_urls.target_stateful_url, clobber=False)
            self._host.reboot()

        # Trigger a second update check (again, test vs MP).
        if self._use_test_image:
            self._trigger_test_update(self._omaha_devserver)
        else:
            # TODO(garnold) chromium-os:33766: use GPIOs to trigger an
            # update.
            pass

        # Observe post-reboot update check, which should indicate that the
        # image version has been updated.
        chain = ExpectedUpdateEventChain(
                (self._WAIT_FOR_UPDATE_CHECK_AFTER_REBOOT_SECONDS,
                 ExpectedUpdateEvent(
                     event_type='update_complete',
                     event_result='success_reboot',
                     version=test_conf['target_release'],
                     previous_version=test_conf['source_release'])))
        if not log_verifier.verify_expected_event_chain(chain):
            self._log_error_and_fail(
                 'after reboot, update engine did not report it had just '
                 'updated.')

        # On test images, make sure we're using a different partition after
        # the update.
        if self._use_test_image:
            target_rootfs_partition = self._get_rootdev()
            if target_rootfs_partition == source_rootfs_partition:
                raise error.TestFail(
                        'rootfs partition did not change (%s)' %
                        target_rootfs_partition)

            logging.info('target image rootfs partition: %s',
                         target_rootfs_partition)

