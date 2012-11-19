# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import socket
import subprocess
import tempfile
import time
import urllib2
import urlparse

from autotest_lib.client.common_lib import error, global_config, site_utils
from autotest_lib.client.common_lib.cros import autoupdater, dev_server
from autotest_lib.server import test


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

        @params actual_event: a dictionary containing event attributes

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
        """Verify a given event chain."""
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

        @raise error.TestError when things go wrong.

        """
        # First, obtain the target URL base / image strings.
        if not update_payload_lorry_url:
            raise error.TestError('missing update payload url')
        update_payload_url_base, update_payload_path, _ = self._split_url(
                update_payload_lorry_url)

        # Second, compute a unique port for the DUT update checks to use, based
        # on the DUT's IP address.
        self._omaha_port = self._get_unique_port(dut_ip_addr)
        logging.debug('dut ip addr: %s => omaha/devserver port: %d',
                      dut_ip_addr, self._omaha_port)

        # Invoke the Omaha/devserver.
        cmdlist = [
                './devserver.py',
                '--archive_dir=static/',
                '--payload=%s' % update_payload_path,
                '--port=%d' % self._omaha_port,
                '--remote_payload',
                '--urlbase=%s' % update_payload_url_base,
                '--max_updates=1',
                '--host_log',
        ]
        logging.info('launching omaha/devserver on %s (%s): %s',
                     omaha_host, devserver_dir, ' '.join(cmdlist))
        # TODO(garnold) invoke omaha/devserver remotely! The host needs to be
        # either globally known to all DUTs, or inferrable based on the DUT's
        # own IP address, or otherwise provisioned to it.
        is_omaha_devserver_local = (
                omaha_host in ['localhost', socket.gethostname()])
        if not is_omaha_devserver_local:
          raise error.TestError(
              'remote omaha/devserver invocation unsupported yet')
        # We are using subprocess directly (as opposed to existing util
        # wrappers like utils.run() or utils.BgJob) because we need to be able
        # to terminate the subprocess once the test finishes.
        devserver_output_namedtemp = tempfile.NamedTemporaryFile()
        self._devserver = subprocess.Popen(
                cmdlist, stdin=subprocess.PIPE,
                stdout=devserver_output_namedtemp.file,
                stderr=subprocess.STDOUT, cwd=devserver_dir or None)
        timeout = self._WAIT_FOR_DEVSERVER_STARTED_SECONDS
        devserver_output_log = []
        with open(devserver_output_namedtemp.name, 'r') as devserver_output:
            while timeout > 0 and self._devserver.returncode is None:
                time.sleep(self._WAIT_SLEEP_INTERVAL)
                timeout -= self._WAIT_SLEEP_INTERVAL
                devserver_started = False
                while not devserver_started:
                    line = devserver_output.readline()
                    if not line:
                        break
                    log_line = '[devserver]' + line.rstrip('\n')
                    logging.debug(log_line)
                    devserver_output_log.append(log_line)
                    devserver_started = 'Bus STARTED' in line
                else:
                    break
            else:
                raise error.TestError(
                    'omaha/devserver not running, error log:\n%s' %
                    '\n'.join(devserver_output_log))

        self._omaha_host = site_utils.externalize_host(omaha_host)


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


    def get_netloc(self):
        if not self._devserver:
            raise error.TestError('no running omaha/devserver')
        return '%s:%s' % (self._omaha_host, self._omaha_port)


    def kill(self):
        """Kill private devserver, wait for it to die."""
        if not self._devserver:
            raise error.TestError('no running omaha/devserver')
        logging.info('killing omaha/devserver')
        self._devserver.terminate()
        self._devserver.communicate()
        self._devserver = None


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
    _WAIT_AFTER_SHUTDOWN_SECONDS        = 10
    _WAIT_AFTER_UPDATE_SECONDS          = 20
    _WAIT_FOR_USB_INSTALL_SECONDS       = 4 * 60
    _WAIT_FOR_MP_RECOVERY_SECONDS       = 8 * 60
    _WAIT_FOR_INITIAL_UPDATE_CHECK_SECONDS = 12 * 60
    _WAIT_FOR_DOWNLOAD_STARTED_SECONDS     = 2 * 60
    _WAIT_FOR_DOWNLOAD_COMPLETED_SECONDS   = 5 * 60
    _WAIT_FOR_UPDATE_COMPLETED_SECONDS     = 4 * 60
    _WAIT_FOR_UPDATE_CHECK_AFTER_REBOOT_SECONDS = 15 * 60
    _DEVSERVER_HOSTLOG_REQUEST_TIMEOUT_SECONDS = 30

    # Omaha event types/results, from update_engine/omaha_request_action.h
    EVENT_TYPE_UNKNOWN           = 0
    EVENT_TYPE_DOWNLOAD_COMPLETE = 1
    EVENT_TYPE_INSTALL_COMPLETE  = 2
    EVENT_TYPE_UPDATE_COMPLETE   = 3
    EVENT_TYPE_DOWNLOAD_STARTED  = 13
    EVENT_TYPE_DOWNLOAD_FINISHED = 14
    EVENT_RESULT_ERROR           = 0
    EVENT_RESULT_SUCCESS         = 1
    EVENT_RESULT_SUCCESS_REBOOT  = 2
    EVENT_RESULT_UPDATE_DEFERRED = 9


    def _servo_dut_power_up(self, host, is_dev_mode):
        """Powers up the DUT, optionally simulating a Ctrl-D key press."""
        host.servo.power_short_press()
        if is_dev_mode:
            host.servo.pass_devmode()


    def _servo_dut_reboot(self, host, is_dev_mode, is_using_test_images,
                          is_disable_usb_hub=False):
        """Reboots a DUT.

        @param host: a host object
        @param is_dev_mode: whether or not the DUT is in dev mode
        @param is_using_test_images: whether or not a test image should be
               assumed
        @param is_disable_usb_hub: disabled the servo USB hub in between power
               off/on cycles; this is useful when (for example) a USB booted
               device need not see the attached USB key after the reboot.

        @raise error.TestFail if DUT fails to reboot.

        """
        logging.info('rebooting dut')
        host.servo.power_long_press()
        _wait(self._WAIT_AFTER_SHUTDOWN_SECONDS, 'after shutdown')
        if is_disable_usb_hub:
            host.servo.disable_usb_hub()
        self._servo_dut_power_up(host, is_dev_mode)
        if is_using_test_images:
            if not host.wait_up(timeout=host.BOOT_TIMEOUT):
                raise error.TestFail(
                        'dut %s failed to boot after %d secs' %
                        (host.ip, host.BOOT_TIMEOUT))
        else:
          # TODO(garnold) chromium-os:33766: implement waiting for MP-signed
          # images; ideas include waiting for a ping reply, or using a GPIO
          # signal.
          pass


    def _install_mp_image(self, host, lorry_image_url, is_dev_mode):
        """Installs an MP-signed recovery image on a DUT.

        @param host: a host object
        @param lorry_image_url: URL of the image on a Lorry/devserver
        @param is_dev_nmode: whether or not the DUT is in dev mode

        """
        # Flash DUT with source image version, using recovery.
        logging.info('installing source mp-signed image via recovery: %s',
                     lorry_image_url)
        host.servo.install_recovery_image(
                lorry_image_url,
                wait_timeout=self._WAIT_FOR_MP_RECOVERY_SECONDS)

        # Reboot the DUT after installation.
        self._servo_dut_reboot(host, is_dev_mode, False,
                               is_disable_usb_hub=True)


    def _install_test_image(self, host, lorry_image_url, is_dev_mode):
        """Installs a test image on a DUT, booted via recovery.

        @param host: a host object
        @param lorry_image_url: URL of the image on a Lorry/devserver
        @param is_dev_nmode: whether or not the DUT is in dev mode

        @raise error.TestFail if DUT cannot boot the test image from USB;
               AutotestHostRunError if failed to run the install command on the
               DUT.

        """
        logging.info('installing source test image via recovery: %s',
                     lorry_image_url)
        host.servo.install_recovery_image(lorry_image_url)
        logging.info('waiting for image to boot')
        if not host.wait_up(timeout=host.USB_BOOT_TIMEOUT):
          raise error.TestFail(
              'dut %s boot from usb timed out after %d secs' %
              (host, host.USB_BOOT_TIMEOUT))
        logging.info('installing new image onto ssd')
        try:
            cmd_result = host.run(
                    'chromeos-install --yes',
                    timeout=self._WAIT_FOR_USB_INSTALL_SECONDS,
                    stdout_tee=None, stderr_tee=None)
        except AutotestHostRunError, e:
            # Dump stdout (with stderr) to the error log.
            logging.error('command failed, stderr:\n' + cmd_result.stderr)
            raise

        # Reboot the DUT after installation.
        self._servo_dut_reboot(host, is_dev_mode, True,
                               is_disable_usb_hub=True)


    def _trigger_test_update(self, host, omaha_netloc):
        """Trigger an update check on a test image.

        Uses update_engine_client via SSH. This is an async call, hence a very
        short timeout.

        @param host: a host object
        @param omaha_netloc: the network location of the Omaha/devserver
               (http://host:port)

        @raise RootFSUpdateError if anything went wrong.

        """
        omaha_update_url = urlparse.urlunsplit(
                ['http', omaha_netloc, '/update', '', ''])
        updater = autoupdater.ChromiumOSUpdater(omaha_update_url, host=host)
        updater.trigger_update()


    def stage_image(self, lorry_devserver, image_uri, board, release, branch,
                    is_using_test_images):
        """Stage a Chrome OS image on Lorry/devserver.

        @return URL of the staged image on the server.

        @raise error.TestError if there's a problem with staging.

        """
        staged_url = None
        if is_using_test_images:
            # For this call, we just need the URL path up to the image.zip file
            # (exclusive).
            image_uri_path = urlparse.urlsplit(image_uri).path.partition(
                    'image.zip')[0].strip('/')
            try:
                lorry_devserver.trigger_test_image_download(image_uri_path)
                staged_url = lorry_devserver.get_test_image_url(
                        board, release, branch)
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


    def stage_payload(self, lorry_devserver, payload_uri, board, release,
                      branch, is_using_test_images, is_delta, is_nton):
        """Stage an update target payload on Lorry/devserver.

        @return URL of the staged payload on the server.

        @raise error.TestError if there's a problem with staging.

        """
        staged_url = None
        if is_using_test_images:
            # For this call, we'll need the URL path without the payload file
            # name.
            payload_uri_path = urlparse.urlsplit(payload_uri).path.rsplit(
                    '/', 1)[0].strip('/')
            try:
                lorry_devserver.trigger_download(payload_uri_path)
                if is_delta:
                    staged_url = lorry_devserver.get_delta_payload_url(
                            'nton' if is_nton else 'mton',
                            board, release, branch)
                else:
                    staged_url = lorry_devserver.get_full_payload_url(
                            board, release, branch)
            except dev_server.DevServerException, e:
                raise error.TestError(
                        'failed to stage target test payload: %s' % e)
        else:
            # TODO(garnold) chromium-os:33766: implement staging of MP-signed
            # images.
            pass

        if not staged_url:
            raise error.TestError('staged target test payload url missing')
        return staged_url


    def run_once(self, host, test_conf):
        """Performs a complete auto update test.

        @param host: a host object representing the DUT
        @param test_conf: a dictionary containing test configuration values

        @raise error.TestError if anything went wrong with setting up the test;
               error.TestFail if any part of the test has failed.

        """
        is_using_test_images = test_conf.get('image_type') != 'mp'
        omaha_host = test_conf.get('omaha_host')

        # Check whether the DUT is in dev mode.
        is_dev_mode = host.servo.get('dev_mode') == 'on'

        # Stage source images and update payloads on lorry/devserver. We use
        # the payload URI as argument for the lab's devserver load-balancing
        # mechanism.
        lorry_devserver = dev_server.ImageServer.resolve(
                test_conf['target_payload_uri'])
        logging.info('staging image and payload on lorry/devserver (%s)',
                     lorry_devserver.url())
        test_conf['source_image_lorry_url'] = self.stage_image(
                lorry_devserver, test_conf['source_image_uri'],
                test_conf['board'], test_conf['source_release'],
                test_conf['source_branch'], is_using_test_images)
        test_conf['target_payload_lorry_url'] = self.stage_payload(
                lorry_devserver, test_conf['target_payload_uri'],
                test_conf['board'], test_conf['target_release'],
                test_conf['target_branch'], is_using_test_images,
                test_conf['update_type'] == 'delta',
                test_conf['target_release'] == test_conf['source_release'])

        # Get the devserver directory from autotest config.
        devserver_dir = global_config.global_config.get_config_value(
                'CROS', 'devserver_dir', default=None)
        if devserver_dir is None:
            raise error.TestError(
                    'path to devserver source tree not provided; please define '
                    'devserver_dir under [CROS] in your shadow_config.ini')

        # Launch Omaha/devserver.
        try:
            self._omaha_devserver = OmahaDevserver(
                    omaha_host, devserver_dir, host.ip,
                    test_conf.get('target_payload_lorry_url'))
        except error.TestError, e:
            logging.error('failed to start omaha/devserver: %s', e)
            raise

        try:
            # Install source image (test vs MP).
            if is_using_test_images:
                self._install_test_image(
                        host, test_conf['source_image_lorry_url'],
                        is_dev_mode)
            else:
                self._install_mp_image(test_conf['source_image_lorry_url'],
                                       is_dev_mode)

            omaha_netloc = self._omaha_devserver.get_netloc()

            # Trigger an update (test vs MP).
            if is_using_test_images:
                self._trigger_test_update(host, omaha_netloc)
            else:
                # TODO(garnold) chromium-os:33766: use GPIOs to trigger an
                # update.
                pass

            # Track update progress.
            omaha_hostlog_url = urlparse.urlunsplit(
                    ['http', omaha_netloc, '/api/hostlog', 'ip=' + host.ip, ''])
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
            self._servo_dut_reboot(host, is_dev_mode, is_using_test_images)

            # Trigger a second update check (again, test vs MP).
            if is_using_test_images:
                self._trigger_test_update(host, omaha_netloc)
            else:
                # TODO(garnold) chromium-os:33766: use GPIOs to trigger an
                # update.
                pass

            # Observe post-reboot update check, which should indicate that the
            # image version has been updated.  Note that the previous version
            # is currently not reported by AU, as one may have expected; had it
            # been reported, we should have included
            # expect_previous_version=test_conf['source_release'] as well.
            chain = ExpectedUpdateEventChain(
                    (self._WAIT_FOR_UPDATE_CHECK_AFTER_REBOOT_SECONDS,
                     ExpectedUpdateEvent(
                         event_type=self.EVENT_TYPE_UPDATE_COMPLETE,
                         event_result=self.EVENT_RESULT_SUCCESS_REBOOT,
                         version=test_conf['target_release'])))
            if not log_verifier.verify_expected_event_chain(chain):
                raise error.TestFail('could not verify that machine rebooted '
                                     'after update')

        except error.TestFail:
            raise
        except Exception, e:
            # Convert any other exception into a test failure.
            raise error.TestFail(str(e))

        finally:
            self._omaha_devserver.kill()

