# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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


def _wait(secs, desc=None):
    """Emits a log message and sleeps for a given number of seconds."""
    msg = 'waiting %s seconds' % secs
    if desc:
        msg += ' (%s)' % desc
    logging.info(msg)
    time.sleep(secs)


class ExpectedUpdateEvent(object):
    """Defines an expected event in a host update process."""
    def __init__(self, event_type=None, event_result=None, version=None,
                 previous_version=None):
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
        if not (actual_attr_val and
                str(actual_attr_val) == str(expected_attr_val)):
            if ('version' in attr_name and actual_attr_val and expected_attr_val
                    in actual_attr_val):
                # We allow for version like 2940.0.0 in 2940.0.0-a1 to allow
                # this test to pass for developer images and non-release images.
                logging.info("Expected version %s in %s but doesn't "
                             "match exactly")
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


class OmahaDevserver(object):
    """Spawns a test-private devserver instance."""
    _WAIT_FOR_DEVSERVER_STARTED_SECONDS = 15
    _WAIT_SLEEP_INTERVAL = 1


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


    def start_devserver(self):
        """Starts the devserver and stores the remote pid in self._devserver_pid
        """
        update_payload_url_base, update_payload_path, _ = self._split_url(
                self._update_payload_lorry_url)
        # Invoke the Omaha/devserver on the remote server.
        cmdlist = [
                '%s/devserver.py' % self._devserver_dir,
                '--archive_dir=static/',
                '--payload=%s' % update_payload_path,
                '--port=%d' % self._omaha_port,
                '--remote_payload',
                '--urlbase=%s' % update_payload_url_base,
                '--max_updates=1',
                '--host_log',
        ]
        # In the remote case that a previous devserver is still running,
        # kill it.
        devserver_pid = self._remote_devserver_pid()
        if devserver_pid:
            logging.warning('Previous devserver still running. Killing.')
            self._kill_devserver_pid(devserver_pid)
            self._devserver_ssh.run('rm -f %s' % self._devserver_output,
                                    ignore_status=True)

        remote_cmd = '( %s ) </dev/null >%s 2>&1 & echo $!' % (
                ' '.join(cmdlist), self._devserver_output)
        logging.info('Starting devserver with %r', remote_cmd)
        self._devserver_pid = self._devserver_ssh.run_output(remote_cmd)


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


    def wait_for_devserver_to_start(self):
        """Returns True if the devserver has started within the time limit."""
        logging.warning('Waiting for devserver to start up.')
        timeout = self._WAIT_FOR_DEVSERVER_STARTED_SECONDS
        netloc = self.get_netloc()
        current_time = time.time()
        deadline = current_time + timeout
        while(current_time < deadline):
            if dev_server.DevServer.devserver_up('http://%s' % netloc,
                                                 timeout_min=0.1):
                return True

            time.sleep(self._WAIT_SLEEP_INTERVAL)
            current_time = time.time()
        else:
            self.dump_devserver_log()
            return False


    def get_netloc(self):
        """Returns the netloc (host:port) of the devserver."""
        if not self._devserver_pid:
            raise error.TestError('no running omaha/devserver')


        return '%s:%s' % (self._omaha_host, self._omaha_port)


    def dump_devserver_log(self, logging_level=logging.ERROR):
        """Dump the devserver log to the autotest log.

        @param logging_level: logging level (from logging) to log the output.
        """
        if self._devserver_pid:
            logging.log(logging_level, self._devserver_ssh.run_output(
                    'cat %s' % self._devserver_output))


    @staticmethod
    def _split_url(url):
        """Splits a URL into the URL base, path and file name."""
        split_url = urlparse.urlsplit(url)
        url_base = urlparse.urlunsplit(
                [split_url.scheme, split_url.netloc, '', '', ''])
        url_path = url_file = ''
        if split_url.path:
            url_path, url_file = split_url.path.rsplit('/', 1)
        return url_base, url_path.lstrip('/'), url_file


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
    _WAIT_FOR_DOWNLOAD_STARTED_SECONDS = 2 * 60
    _WAIT_FOR_DOWNLOAD_COMPLETED_SECONDS = 10 * 60
    _WAIT_FOR_UPDATE_COMPLETED_SECONDS = 4 * 60
    _WAIT_FOR_UPDATE_CHECK_AFTER_REBOOT_SECONDS = 15 * 60
    _DEVSERVER_HOSTLOG_REQUEST_TIMEOUT_SECONDS = 30

    # Omaha event types/results, from update_engine/omaha_request_action.h
    EVENT_TYPE_UNKNOWN = 0
    EVENT_TYPE_DOWNLOAD_COMPLETE = 1
    EVENT_TYPE_INSTALL_COMPLETE = 2
    EVENT_TYPE_UPDATE_COMPLETE = 3
    EVENT_TYPE_DOWNLOAD_STARTED = 13
    EVENT_TYPE_DOWNLOAD_FINISHED = 14
    EVENT_RESULT_ERROR = 0
    EVENT_RESULT_SUCCESS = 1
    EVENT_RESULT_SUCCESS_REBOOT = 2
    EVENT_RESULT_UPDATE_DEFERRED = 9


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


    def _trigger_test_update(self, omaha_netloc):
        """Trigger an update check on a test image.

        Uses update_engine_client via SSH. This is an async call, hence a very
        short timeout.

        @param omaha_netloc: the network location of the Omaha/devserver
               (http://host:port)

        @raise RootFSUpdateError if anything went wrong.

        """
        omaha_update_url = urlparse.urlunsplit(
                ['http', omaha_netloc, '/update', '', ''])
        updater = autoupdater.ChromiumOSUpdater(omaha_update_url,
                                                host=self._host)
        updater.trigger_update()


    def _get_rootdev(self):
        """Returns the partition device containing the rootfs on a host.

        @return The rootfs partition device (string).

        @raise AutotestHostRunError if command failed to run on host.

        """
        # This command should return immediately, hence the short timeout.
        return self._host.run('rootdev -s', timeout=10).stdout.strip()


    def stage_image(self, lorry_devserver, image_uri):
        """Stage a Chrome OS image on Lorry/devserver.

        @param lorry_devserver: instance of client.common_lib.dev_server to use
                                to reach the devserver instance for this build.
        @param image_uri: The uri of the image.
        @return URL of the staged image on the server.

        @raise error.TestError if there's a problem with staging.

        """
        staged_url = None
        if self._use_test_image:
            # For this call, we just need the URL path up to the image.zip file
            # (exclusive).
            image_uri_path = urlparse.urlsplit(image_uri).path.partition(
                    'image.zip')[0].strip('/')
            try:
                lorry_devserver.stage_artifacts(image_uri_path, ['test_image'])
                staged_url = lorry_devserver.get_test_image_url(image_uri_path)
            except dev_server.DevServerException, e:
                raise error.TestError(
                        'failed to stage source test image: %s' % e)
        else:
            # TODO(garnold) chromium-os:33766: implement staging of MP-signed
            # images.
            pass

        if not staged_url:
            raise error.TestError('staged source test image url missing')
        return staged_url


    def stage_payload(self, lorry_devserver, payload_uri, is_delta, is_nton):
        """Stage an update target payload on Lorry/devserver.

        @param lorry_devserver: instance of client.common_lib.dev_server to use
                                to reach the devserver instance for this build.
        @param payload_uri: The uri of the payload.
        @param is_delta: If true, this payload is a delta payload.
        @param is_nton: If true, this payload is an nplus1 payload.

        @return URL of the staged payload on the server.

        @raise error.TestError if there's a problem with staging.

        """
        staged_url = None
        if self._use_test_image:
            # For this call, we'll need the URL path without the payload file
            # name.
            payload_uri_path = urlparse.urlsplit(payload_uri).path.rsplit(
                    '/', 1)[0].strip('/')
            try:
                if is_delta:
                    lorry_devserver.stage_artifacts(
                            payload_uri_path, ['delta_payloads', 'stateful'])
                    staged_url = lorry_devserver.get_delta_payload_url(
                            'nton' if is_nton else 'mton', payload_uri_path)
                else:
                    lorry_devserver.stage_artifacts(
                            payload_uri_path, ['full_payload', 'stateful'])
                    staged_url = lorry_devserver.get_full_payload_url(
                            payload_uri_path)
            except dev_server.DevServerException, e:
                raise error.TestError('failed to stage test payload: %s' % e)
        else:
            # TODO(garnold) chromium-os:33766: implement staging of MP-signed
            # images.
            pass

        if not staged_url:
            raise error.TestError('staged test payload url missing')

        return staged_url


    def _payload_to_update_url(self, payload_url):
        """Given a payload url, returns the Update Engine update url for it."""
         # image_url is of the format that is in the devserver i.e.
        # <hostname>/static/archive/...LABEL/update.gz.
        # We want to transform it to the correct omaha url which is
        # <hostname>/update/...LABEL.
        update_url = payload_url.rpartition('/update.gz')[0]
        return update_url.replace('/static/archive/', '/update/')


    def _install_source_image(self, image_url):
        """Prepare the specified host with the image."""
        if self._use_servo:
            # Install source image (test vs MP).
            if self._use_test_image:
                self._install_test_image_with_servo(image_url)
            else:
                self._install_mp_image(image_url)

        else:
            self._host.machine_install(self._payload_to_update_url(image_url),
                                       force_update=True)


    def _stage_images_onto_devserver(self, lorry_devserver, test_conf):
        """Stages images that will be used by the test onto the devserver.

        @return a tuple containing the urls of the source and target payloads.
        """
        logging.info('staging images onto lorry/devserver (%s)',
                     lorry_devserver.url())

        source_url = None
        if self._use_servo:
            source_url = self.stage_image(
                    lorry_devserver, test_conf['source_image_uri'])
            logging.info('test image for source image staged at %s', source_url)
        else:
            source_url = self.stage_payload(
                    lorry_devserver, test_conf['source_image_uri'], False,
                    False)
            logging.info('full payload for source image staged at %s',
                         source_url)

        target_url = self.stage_payload(
                lorry_devserver, test_conf['target_payload_uri'],
                test_conf['update_type'] == 'delta',
                test_conf['target_release'] == test_conf['source_release'])
        logging.info('%s payload for update test staged at %s',
                     test_conf['update_type'], target_url)
        return source_url, target_url


    def initialize(self):
        """Sets up variables that will be used by test."""
        self._host = None
        self._use_servo = False
        self._dev_mode = False
        self._omaha_devserver = None

        self._use_test_image = True
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


    def _verify_preconditions(self, test_conf):
        """Validate input args make sense."""
        if self._use_servo and not self._host.servo:
            raise error.AutotestError('Servo use specified but no servo '
                                      'attached to host object.')

        if not self._use_test_image and not self._use_servo:
            raise error.TestError("Can't install mp image without servo.")


    def run_once(self, host, test_conf, use_servo):
        """Performs a complete auto update test.

        @param host: a host object representing the DUT
        @param test_conf: a dictionary containing test configuration values
        @param use_servo: True whether we should use servo.

        @raise error.TestError if anything went wrong with setting up the test;
               error.TestFail if any part of the test has failed.

        """
        self._host = host
        self._use_test_image = test_conf.get('image_type') != 'mp'
        self._use_servo = use_servo
        if self._use_servo:
            self._dev_mode = self._host.servo.get('dev_mode') == 'on'

        # Verify that our arguments are sane.
        self._verify_preconditions(test_conf)

        # Stage source images and update payloads on lorry/devserver. We use
        # the payload URI as argument for the lab's devserver load-balancing
        # mechanism.
        lorry_devserver = dev_server.ImageServer.resolve(
                test_conf['target_payload_uri'])
        source_url, target_payload_url = self._stage_images_onto_devserver(
                lorry_devserver, test_conf)

        # Install the source image onto the DUT.
        self._install_source_image(source_url)

        # On test images, record the active root partition.
        source_rootfs_partition = None
        if self._use_test_image:
            source_rootfs_partition = self._get_rootdev()
            logging.info('source image rootfs partition: %s',
                         source_rootfs_partition)

        omaha_host = urlparse.urlparse(lorry_devserver.url()).hostname
        self._omaha_devserver = OmahaDevserver(
                omaha_host, self._devserver_dir, self._host.ip,
                target_payload_url)

        self._omaha_devserver.start_devserver()
        self._omaha_devserver.wait_for_devserver_to_start()

        # Trigger an update (test vs MP).
        omaha_netloc = self._omaha_devserver.get_netloc()
        if self._use_test_image:
            self._trigger_test_update(omaha_netloc)
        else:
            # TODO(garnold) chromium-os:33766: use GPIOs to trigger an
            # update.
            pass

        # Track update progress.
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
                     event_type=self.EVENT_TYPE_DOWNLOAD_STARTED,
                     event_result=self.EVENT_RESULT_SUCCESS,
                     version=test_conf['source_release'])),
                (self._WAIT_FOR_DOWNLOAD_COMPLETED_SECONDS,
                 ExpectedUpdateEvent(
                     event_type=self.EVENT_TYPE_DOWNLOAD_FINISHED,
                     event_result=self.EVENT_RESULT_SUCCESS,
                     version=test_conf['source_release'])),
                (self._WAIT_FOR_UPDATE_COMPLETED_SECONDS,
                 ExpectedUpdateEvent(
                     event_type=self.EVENT_TYPE_UPDATE_COMPLETE,
                     event_result=self.EVENT_RESULT_SUCCESS,
                     version=test_conf['source_release'])))

        if not log_verifier.verify_expected_event_chain(chain):
            raise error.TestFail(
                    'could not verify that update was successful')

        # Wait after an update completion (safety margin).
        _wait(self._WAIT_AFTER_UPDATE_SECONDS, 'after update completion')

        # Reboot the DUT after the update.
        if use_servo:
            self._servo_dut_reboot()
        else:
            # Stateful from source may not be compatible with target. Update it.
            update_url = self._payload_to_update_url(target_payload_url)
            updater = autoupdater.ChromiumOSUpdater(update_url, host=self._host)
            updater.update_stateful(clobber=False)
            self._host.reboot()

        # Trigger a second update check (again, test vs MP).
        if self._use_test_image:
            self._trigger_test_update(omaha_netloc)
        else:
            # TODO(garnold) chromium-os:33766: use GPIOs to trigger an
            # update.
            pass

        # Observe post-reboot update check, which should indicate that the
        # image version has been updated.
        chain = ExpectedUpdateEventChain(
                (self._WAIT_FOR_UPDATE_CHECK_AFTER_REBOOT_SECONDS,
                 ExpectedUpdateEvent(
                     event_type=self.EVENT_TYPE_UPDATE_COMPLETE,
                     event_result=self.EVENT_RESULT_SUCCESS_REBOOT,
                     version=test_conf['target_release'],
                     previous_version=test_conf['source_release'])))
        if not log_verifier.verify_expected_event_chain(chain):
            raise error.TestFail('could not verify that machine rebooted '
                                 'after update')

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

