# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import logging
import os
import socket
import time
import urllib2
import urlparse

from autotest_lib.client.bin import utils as client_utils
from autotest_lib.client.common_lib import error, global_config
from autotest_lib.client.common_lib.cros import autoupdater, dev_server
from autotest_lib.server import autotest, hosts, test
from autotest_lib.server.cros.dynamic_suite import tools


def _wait(secs, desc=None):
    """Emits a log message and sleeps for a given number of seconds."""
    msg = 'Waiting %s seconds' % secs
    if desc:
        msg += ' (%s)' % desc
    logging.info(msg)
    time.sleep(secs)


class ExpectedUpdateEventChainFailed(error.TestFail):
    """Raised if we fail to receive an expected event in a chain."""

class RequiredArgumentMissing(error.TestFail):
    """Raised if we fail to receive an expected event in a chain."""


# Update event types.
EVENT_TYPE_DOWNLOAD_COMPLETE = '1'
EVENT_TYPE_INSTALL_COMPLETE = '2'
EVENT_TYPE_UPDATE_COMPLETE = '3'
EVENT_TYPE_DOWNLOAD_STARTED = '13'
EVENT_TYPE_DOWNLOAD_FINISHED = '14'

# Update event results.
EVENT_RESULT_ERROR = '0'
EVENT_RESULT_SUCCESS = '1'
EVENT_RESULT_SUCCESS_REBOOT = '2'
EVENT_RESULT_UPDATE_DEFERRED = '9'


class ExpectedUpdateEvent(object):
    """Defines an expected event in a host update process.

    Attrs:
        _expected_attrs: Dictionary of attributes that should match events
                         received. If attribute is not provided, assumes match.
        error_message: What we should error out with if we fail to verify this
                       expected event.
    """

    # Omaha event types/results, from update_engine/omaha_request_action.h
    # These are stored in dict form in order to easily print out the keys.
    _EVENT_TYPE_DICT = {
            EVENT_TYPE_DOWNLOAD_COMPLETE: 'download_complete',
            EVENT_TYPE_INSTALL_COMPLETE: 'install_complete',
            EVENT_TYPE_UPDATE_COMPLETE: 'update_complete',
            EVENT_TYPE_DOWNLOAD_STARTED: 'download_started',
            EVENT_TYPE_DOWNLOAD_FINISHED: 'download_finished'
    }

    _EVENT_RESULT_DICT = {
            EVENT_RESULT_ERROR: 'error',
            EVENT_RESULT_SUCCESS: 'success',
            EVENT_RESULT_SUCCESS_REBOOT: 'success_reboot',
            EVENT_RESULT_UPDATE_DEFERRED: 'update_deferred'
    }

    _ATTR_NAME_DICT_MAP = {
            'event_type': _EVENT_TYPE_DICT,
            'event_result': _EVENT_RESULT_DICT,
    }

    _VALID_TYPES = set(_EVENT_TYPE_DICT.keys())
    _VALID_RESULTS = set(_EVENT_RESULT_DICT.keys())

    def __init__(self, event_type=None, event_result=None, version=None,
                 previous_version=None, error_message=None):
        if event_type and event_type not in self._VALID_TYPES:
            raise ValueError('event_type %s is not valid.' % event_type)

        if event_result and event_result not in self._VALID_RESULTS:
            raise ValueError('event_result %s is not valid.' % event_result)

        self._expected_attrs = {
            'event_type': event_type,
            'event_result': event_result,
            'version': version,
            'previous_version': previous_version,
        }
        self.error_message = error_message


    @staticmethod
    def _attr_val_str(attr_val, helper_dict, default=None):
        """Returns an enriched attribute value string, or default."""
        if not attr_val:
            return default

        s = str(attr_val)
        if helper_dict:
            s += ':%s' % helper_dict.get(attr_val, 'unknown')

        return s


    def _attr_name_and_values(self, attr_name, expected_attr_val,
                              actual_attr_val=None):
        """Returns an attribute name, expected and actual value strings.

        This will return (name, expected, actual); the returned value for
        actual will be None if its respective input is None/empty.

        """
        helper_dict = self._ATTR_NAME_DICT_MAP.get(attr_name)
        expected_attr_val_str = self._attr_val_str(expected_attr_val,
                                                   helper_dict,
                                                   default='any')
        actual_attr_val_str = self._attr_val_str(actual_attr_val, helper_dict)

        return attr_name, expected_attr_val_str, actual_attr_val_str


    def __str__(self):
        return ' '.join(['%s=%s' %
                         self._attr_name_and_values(attr_name, attr_val)[0:2]
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
            logging.error('No value found for %s (expected %s)',
                          *self._attr_name_and_values(attr_name,
                                                      expected_attr_val)[0:2])
            return False

        # Convert actual value to a string.
        actual_attr_val = str(actual_attr_val)

        if not actual_attr_val == expected_attr_val:
            # We allow expected version numbers (e.g. 2940.0.0) to be contained
            # in actual values (2940.0.0-a1); this is necessary for the test to
            # pass with developer / non-release images.
            if 'version' in attr_name and expected_attr_val in actual_attr_val:
                logging.info('Expected %s (%s) contained in actual value (%s) '
                             'but does not match exactly',
                             *self._attr_name_and_values(
                                     attr_name, expected_attr_val,
                                     actual_attr_val=actual_attr_val))
                return True

            logging.error('Expected %s (%s) different from actual value (%s)',
                          *self._attr_name_and_values(
                                  attr_name, expected_attr_val,
                                  actual_attr_val=actual_attr_val))
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


    @staticmethod
    def _format_event_with_timeout(timeout, expected_event):
        """Returns a string representation of the event, with timeout."""
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

        @raises ExpectedUpdateEventChainFailed if we failed to verify an event.

        """
        for timeout, expected_event in self._expected_event_chain:
            logging.info('Expecting %s',
                         self._format_event_with_timeout(timeout,
                                                         expected_event))
            if not self._verify_event_with_timeout(
                    timeout, expected_event, get_next_event):
                logging.error('Failed expected event: %s',
                              expected_event.error_message)
                raise ExpectedUpdateEventChainFailed(
                        expected_event.error_message)


    @staticmethod
    def _verify_event_with_timeout(timeout, expected_event, get_next_event):
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
                logging.info('Event received after %s seconds',
                             round(curr_timestamp - base_timestamp, 1))
                return expected_event.verify(new_event)

            # No new events, sleep for one second only (so we don't miss
            # events at the end of the allotted timeout).
            time.sleep(1)
            curr_timestamp = time.time()

        logging.error('Timeout expired')
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

        @raises ExpectedUpdateEventChainFailed if we failed to verify the an
                event.
        """
        expected_event_chain.verify(self._get_next_log_event)


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
                logging.warning('Failed to read event log url: %s', e)
                return None
            except socket.timeout, e:
                logging.warning('Timed out reading event log url: %s', e)
                return None

            event_log_resp = conn.read()
            conn.close()
            self._event_log = json.loads(event_log_resp)

        # Return next new event, if one is found.
        if len(self._event_log) > self._num_consumed_events:
            new_event = self._event_log[self._num_consumed_events]
            self._num_consumed_events += 1
            logging.info('Consumed new event: %s', new_event)
            return new_event


class OmahaDevserverFailedToStart(error.TestError):
    """Raised when a omaha devserver fails to start."""


class OmahaDevserver(object):
    """Spawns a test-private devserver instance."""
    # How long to wait for a devserver to start.
    _WAIT_FOR_DEVSERVER_STARTED_SECONDS = 15

    # How long to sleep (seconds) between checks to see if a devserver is up.
    _WAIT_SLEEP_INTERVAL = 1

    # Max devserver execution time (seconds); used with timelimit(1) to ensure
    # we don't have defunct instances hogging the system.
    _DEVSERVER_TIMELIMIT = 12 * 60 * 60


    def __init__(self, omaha_host, devserver_dir, update_payload_staged_url):
        """Starts a private devserver instance, operating at Omaha capacity.

        @param omaha_host: host address where the devserver is spawned.
        @param devserver_dir: path to the devserver source directory
        @param update_payload_staged_url: URL to provision for update requests.

        """
        if not update_payload_staged_url:
            raise error.TestError('Missing update payload url')

        self._omaha_host = omaha_host
        self._devserver_pid = 0
        self._devserver_port = 0  # Determined later from devserver portfile.
        self._devserver_dir = devserver_dir
        self._update_payload_staged_url = update_payload_staged_url

        self._devserver_ssh = hosts.SSHHost(self._omaha_host,
                                            user=os.environ['USER'])

        # Allocate temporary files for various server outputs.
        self._devserver_logfile = self._create_tempfile_on_devserver('log')
        self._devserver_portfile = self._create_tempfile_on_devserver('port')
        self._devserver_pidfile = self._create_tempfile_on_devserver('pid')

    def _create_tempfile_on_devserver(self, label):
        """Creates a temporary file on the devserver and returns its path.

        @param label: Identifier for the file context (string, no whitespaces).

        @raises test.TestError: If we failed to invoke mktemp on the server.
        @raises OmahaDevserverFailedToStart: If tempfile creation failed.
        """
        remote_cmd = 'mktemp --tmpdir devserver-%s.XXXXXX' % label
        try:
            result = self._devserver_ssh.run(remote_cmd, ignore_status=True)
        except error.AutoservRunError as e:
            self._log_and_raise_remote_ssh_error(e)
        if result.exit_status != 0:
            raise OmahaDevserverFailedToStart(
                    'Could not create a temporary %s file on the devserver, '
                    'error output:\n%s' % (label, result.stderr))
        return result.stdout.strip()

    @staticmethod
    def _log_and_raise_remote_ssh_error(e):
        """Logs failure to ssh remote, then raises a TestError."""
        logging.debug('Failed to ssh into the devserver: %s', e)
        logging.error('If you are running this locally it means you did not '
                      'configure ssh correctly.')
        raise error.TestError('Failed to ssh into the devserver: %s' % e)


    def _read_int_from_devserver_file(self, filename):
        """Reads and returns an integer value from a file on the devserver."""
        return int(self._get_devserver_file_content(filename).strip())


    def _wait_for_devserver_to_start(self):
        """Waits until the devserver starts within the time limit.

        Infers and sets the devserver PID and serving port.

        Raises:
            OmahaDevserverFailedToStart: If the time limit is reached and we
                                         cannot connect to the devserver.
        """
        # Compute the overall timeout.
        deadline = time.time() + self._WAIT_FOR_DEVSERVER_STARTED_SECONDS

        # First, wait for port file to be filled and determine the server port.
        logging.warning('Waiting for devserver to start up.')
        while time.time() < deadline:
            try:
                self._devserver_pid = self._read_int_from_devserver_file(
                        self._devserver_pidfile)
                self._devserver_port = self._read_int_from_devserver_file(
                        self._devserver_portfile)
                logging.info('Devserver pid is %d, serving on port %d',
                             self._devserver_pid, self._devserver_port)
                break
            except Exception:  # Couldn't read file or corrupt content.
                time.sleep(self._WAIT_SLEEP_INTERVAL)
        else:
            raise OmahaDevserverFailedToStart(
                    'The test failed to find the pid/port of the omaha '
                    'devserver. Check the dumped devserver logs for more '
                    'information.')

        # Check that the server is reponsding to network requests.
        logging.warning('Waiting for devserver to accept network requests.')
        url = 'http://%s' % self.get_netloc()
        while time.time() < deadline:
            if dev_server.DevServer.devserver_healthy(url, timeout_min=0.1):
                break

            # TODO(milleral): Refactor once crbug.com/221626 is resolved.
            time.sleep(self._WAIT_SLEEP_INTERVAL)
        else:
            raise OmahaDevserverFailedToStart(
                    'The test failed to establish a connection to the omaha '
                    'devserver it set up on port %d. Check the dumped '
                    'devserver logs for more information.' %
                    self._devserver_port)


    def start_devserver(self):
        """Starts the devserver and confirms it is up.

        Raises:
            test.TestError: If we failed to spawn the remote devserver.
            OmahaDevserverFailedToStart: If the time limit is reached and we
                                         cannot connect to the devserver.
        """
        update_payload_url_base, update_payload_path = self._split_url(
                self._update_payload_staged_url)
        # Invoke the Omaha/devserver on the remote server.
        cmdlist = [
                'timelimit', '-T', str(self._DEVSERVER_TIMELIMIT),
                '%s/devserver.py' % self._devserver_dir,
                '--payload=%s' % update_payload_path,
                '--port=0',
                '--pidfile=%s' % self._devserver_pidfile,
                '--portfile=%s' % self._devserver_portfile,
                '--logfile=%s' % self._devserver_logfile,
                '--remote_payload',
                '--urlbase=%s' % update_payload_url_base,
                '--max_updates=1',
                '--host_log',
        ]
        remote_cmd = '( %s ) </dev/null >/dev/null 2>&1 &' % ' '.join(cmdlist)

        logging.info('Starting devserver with %r', remote_cmd)
        try:
            self._devserver_ssh.run_output(remote_cmd)
        except error.AutoservRunError as e:
            self._log_and_raise_remote_ssh_error(e)

        try:
            self._wait_for_devserver_to_start()
        except OmahaDevserverFailedToStart:
            self._kill_remote_process()
            self._dump_devserver_log()
            raise


    def _kill_remote_process(self):
        """Kills the devserver and verifies it's down; clears the remote pid."""
        def devserver_down():
            """Ensure that the devserver process is down."""
            return not self._remote_process_alive()

        if devserver_down():
            return

        for signal in 'SIGTERM', 'SIGKILL':
            remote_cmd = 'kill -s %s %s' % (signal, self._devserver_pid)
            self._devserver_ssh.run(remote_cmd)
            try:
                client_utils.poll_for_condition(
                        devserver_down, sleep_interval=1, desc='devserver down')
                break
            except client_utils.TimeoutError:
                logging.warning('Could not kill devserver with %s.', signal)
        else:
            logging.warning('Failed to kill devserver, giving up.')

        self._devserver_pid = None


    def _remote_process_alive(self):
        """Tests whether the remote devserver process is running."""
        if not self._devserver_pid:
            return False
        remote_cmd = 'test -e /proc/%s' % self._devserver_pid
        result = self._devserver_ssh.run(remote_cmd, ignore_status=True)
        return result.exit_status == 0


    def get_netloc(self):
        """Returns the netloc (host:port) of the devserver."""
        if not (self._devserver_pid and self._devserver_port):
            raise error.TestError('No running omaha/devserver')

        return '%s:%s' % (self._omaha_host, self._devserver_port)


    def get_update_url(self):
        """Returns the update_url you can use to update via this server."""
        return urlparse.urlunsplit(('http', self.get_netloc(), '/update',
                                    '', ''))


    def _get_devserver_file_content(self, filename):
        """Returns the content of a file on the devserver."""
        return self._devserver_ssh.run_output('cat %s' % filename)


    def _get_devserver_log(self):
        """Obtain the devserver output."""
        return self._get_devserver_file_content(self._devserver_logfile)


    def _dump_devserver_log(self, logging_level=logging.ERROR):
        """Dump the devserver log to the autotest log, then remove the log file.

        @param logging_level: logging level (from logging) to log the output.
        """
        logging.log(logging_level, self._get_devserver_log())
        self._devserver_ssh.run('rm -f %s' % self._devserver_logfile)


    @staticmethod
    def _split_url(url):
        """Splits a URL into the URL base and path."""
        split_url = urlparse.urlsplit(url)
        url_base = urlparse.urlunsplit(
                (split_url.scheme, split_url.netloc, '', '', ''))
        url_path = split_url.path
        return url_base, url_path.lstrip('/')


    def stop_devserver(self):
        """Kill remote process and wait for it to die, dump its output."""
        if not self._devserver_pid:
            logging.error('No running omaha/devserver.')
            return

        logging.info('Killing omaha/devserver')
        self._kill_remote_process()
        logging.debug('Final devserver log before killing')
        self._dump_devserver_log(logging.DEBUG)


class autoupdate_EndToEndTest(test.test):
    """Complete update test between two Chrome OS releases.

    Performs an end-to-end test of updating a ChromeOS device from one version
    to another. This script requires a running (possibly remote) servod
    instance connected to an actual servo board, which controls the DUT. It
    also assumes that a corresponding target (update) image was staged for
    download on a central staging devserver.

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

    Some notes on naming:
      devserver: Refers to a machine running the Chrome OS Update Devserver.
      autotest_devserver: An autotest wrapper to interact with a devserver.
                          Can be used to stage artifacts to a devserver. While
                          this can also be used to update a machine, we do not
                          use it for that purpose in this test as we manage
                          updates with out own devserver instances (see below).
      omaha_devserver: This test's wrapper of a devserver running for the
                       purposes of emulating omaha. This test controls the
                       lifetime of this devserver instance and is separate
                       from the autotest lab's devserver's instances which are
                       only used for staging and hosting artifacts (because they
                       scale). These are run on the same machines as the actual
                       autotest devservers which are used for staging but on
                       different ports.
      *staged_url's: In this case staged refers to the fact that these items
                     are available to be downloaded statically from these urls
                     e.g. 'localhost:8080/static/my_file.gz'. These are usually
                     given after staging an artifact using a autotest_devserver
                     though they can be re-created given enough assumptions.
      *update_url's: Urls refering to the update RPC on a given omaha devserver.
                     Since we always use an instantiated omaha devserver to run
                     updates, these will always reference an existing instance
                     of an omaha devserver that we just created for the purposes
                     of updating.
      devserver_hostname: At the start of each test, we choose a devserver
                          machine in the lab for the test. We use the devserver
                          instance there (access by autotest_devserver) to stage
                          artifacts. However, we also use the same host to start
                          omaha devserver instances for updating machines with
                          (that reference the staged paylaods on the autotest
                          devserver instance). This hostname refers to that
                          machine we are using (since it's always the same for
                          both staging/omaha'ing).

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

    _STATEFUL_UPDATE_FILENAME = 'stateful.tgz'

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
        logging.info('Rebooting dut')
        self._host.servo.power_long_press()
        _wait(self._WAIT_AFTER_SHUTDOWN_SECONDS, 'after shutdown')
        if disconnect_usbkey:
            self._host.servo.switch_usbkey('host')

        self._servo_dut_power_up()
        if self._use_test_image:
            if not self._host.wait_up(timeout=self._host.BOOT_TIMEOUT):
                raise error.TestFail(
                        'DUT %s failed to boot after %d secs' %
                        (self._host.ip, self._host.BOOT_TIMEOUT))
        else:
            # TODO(garnold) chromium-os:33766: implement waiting for MP-signed
            # images; ideas include waiting for a ping reply, or using a GPIO
            # signal.
            pass


    def _install_mp_image(self, staged_image_url):
        """Installs an MP-signed recovery image on a DUT.

        @param staged_image_url: URL of the image on a Lorry/devserver
        """
        # Flash DUT with source image version, using recovery.
        logging.info('Installing source mp-signed image via recovery: %s',
                     staged_image_url)
        self._host.servo.install_recovery_image(
                staged_image_url,
                wait_timeout=self._WAIT_FOR_MP_RECOVERY_SECONDS)

        # Reboot the DUT after installation.
        self._servo_dut_reboot(disconnect_usbkey=True)


    def _install_test_image_with_servo(self, staged_image_url):
        """Installs a test image on a DUT, booted via recovery.

        @param staged_image_url: URL of the image on the devserver
        @param is_dev_nmode: whether or not the DUT is in dev mode

        @raise error.TestFail if DUT cannot boot the test image from USB;
               AutotestHostRunError if failed to run the install command on the
               DUT.

        """
        logging.info('Installing source test image via recovery: %s',
                     staged_image_url)
        self._host.servo.install_recovery_image(staged_image_url)
        logging.info('Waiting for image to boot')
        if not self._host.wait_up(timeout=self._host.USB_BOOT_TIMEOUT):
            raise error.TestFail(
                    'DUT %s boot from usb timed out after %d secs' %
                    (self._host, self._host.USB_BOOT_TIMEOUT))
        logging.info('Installing new image onto ssd')
        try:
            cmd_result = self._host.run(
                    'chromeos-install --yes',
                    timeout=self._WAIT_FOR_USB_INSTALL_SECONDS,
                    stdout_tee=None, stderr_tee=None)
        except error.AutotestHostRunError:
            # Dump stdout (with stderr) to the error log.
            logging.error('Command failed, stderr:\n' + cmd_result.stderr)
            raise

        # Reboot the DUT after installation.
        self._servo_dut_reboot(disconnect_usbkey=True)


    def _trigger_test_update(self, omaha_devserver):
        """Trigger an update check on a test image.

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
        return self._host.run('rootdev -s').stdout.strip()


    def _stage_image(self, autotest_devserver, image_uri):
        """Stage a Chrome OS image onto a staging devserver.

        @param autotest_devserver: instance of client.common_lib.dev_server to
                                   use to stage the image.
        @param image_uri: The uri of the image.
        @return URL of the staged image on the staging devserver.

        @raise error.TestError if there's a problem with staging.

        """
        if self._use_test_image:
            # For this call, we just need the URL path up to the image.zip file
            # (exclusive).
            image_uri_path = urlparse.urlsplit(image_uri).path.partition(
                    'image.zip')[0].strip('/')
            try:
                autotest_devserver.stage_artifacts(image_uri_path,
                                                   ['test_image'])
                return autotest_devserver.get_test_image_url(image_uri_path)
            except dev_server.DevServerException, e:
                raise error.TestError(
                        'Failed to stage source test image: %s' % e)
        else:
            # TODO(garnold) chromium-os:33766: implement staging of MP-signed
            # images.
            raise NotImplementedError()


    @staticmethod
    def _stage_payload(autotest_devserver, devserver_label, filename,
                       archive_url=None):
        """Stage the given payload onto the devserver.

        Works for either a stateful or full/delta test payload. Expects the
        gs_path or a combo of devserver_label + filename.

        @param autotest_devserver: instance of client.common_lib.dev_server to
                                   use to reach the devserver instance for this
                                   build.
        @param devserver_label: The build name e.g. x86-mario-release/<version>.
                                If set, assumes default gs archive bucket and
                                requires filename to be specified.
        @param filename: In conjunction with devserver_label, if just specifying
                         the devserver label name, this is which file are you
                         downloading.
        @param archive_url: An optional GS archive location, if not using the
                            devserver's default.

        @return URL of the staged payload on the server.

        @raise error.TestError if there's a problem with staging.

        """
        try:
            autotest_devserver.stage_artifacts(
                    image=devserver_label, files=[filename],
                    archive_url=archive_url)
            return autotest_devserver.get_staged_file_url(filename,
                                                          devserver_label)
        except dev_server.DevServerException, e:
            raise error.TestError('Failed to stage payload: %s' % e)


    def _stage_payload_by_uri(self, autotest_devserver, payload_uri):
        """Stage a payload based on its GS URI.

        This infers the build's label, filename and GS archive from the
        provided GS URI.

        @param autotest_devserver: instance of client.common_lib.dev_server to
                                   use to reach the devserver instance for this
                                   build.
        @param payload_uri: The full GS URI of the payload.

        @return URL of the staged payload on the server.

        @raise error.TestError if there's a problem with staging.

        """
        archive_url, _, filename = payload_uri.rpartition('/')
        devserver_label = urlparse.urlsplit(archive_url).path.strip('/')
        return self._stage_payload(autotest_devserver, devserver_label,
                                   filename, archive_url=archive_url)


    @staticmethod
    def _payload_to_update_url(payload_url):
        """Given a update or stateful payload url, returns the update url."""
        # We want to transform it to the correct omaha url which is
        # <hostname>/update/...LABEL.
        base_url = payload_url.rpartition('/')[0]
        return base_url.replace('/static/', '/update/')


    def _get_stateful_uri(self, build_uri):
        """Returns a complete GS URI of a stateful update given a build path."""
        return '/'.join([build_uri.rstrip('/'), self._STATEFUL_UPDATE_FILENAME])


    def _payload_to_stateful_uri(self, payload_uri):
        """Given a payload GS URI, returns the corresponding stateful URI."""
        build_uri = payload_uri.rpartition('/')[0]
        return self._get_stateful_uri(build_uri)


    def update_via_test_payloads(self, omaha_host, payload_url, stateful_url,
                                 clobber):
        """Given the following update and stateful urls, update the DUT.

        Only updates the rootfs/stateful if the respective url is provided.

        @param omaha_host: If updating rootfs, redirect updates through this
            host. Should be None iff payload_url is None.
        @param payload_url: If set, the specified url to find the update
            payload.
        @param stateful_url: If set, the specified url to find the stateful
            payload.
        @param clobber: If True, do a clean install of stateful.
        """
        def perform_update(url, is_stateful):
            """Perform a rootfs/stateful update using given URL.

            @param url: URL to update from.
            @param is_stateful: Whether this is a stateful or rootfs update.
            """
            if url:
                updater = autoupdater.ChromiumOSUpdater(url, host=self._host)
                if is_stateful:
                    updater.update_stateful(clobber=clobber)
                else:
                    updater.update_rootfs()

        # We create a OmahaDevserver to redirect blah.bin to update/. This
        # allows us to use any payload filename to serve an update.
        temp_devserver = None
        try:
            if payload_url:
                temp_devserver = OmahaDevserver(
                        omaha_host, self._devserver_dir, payload_url)
                temp_devserver.start_devserver()
                payload_url = temp_devserver.get_update_url()

            stateful_url = self._payload_to_update_url(stateful_url)

            perform_update(payload_url, False)
            perform_update(stateful_url, True)
        finally:
            if temp_devserver:
                temp_devserver.stop_devserver()


    def install_source_version(self, devserver_hostname, image_url,
                               stateful_url):
        """Prepare the specified host with the image given by the urls.

        @param devserver_hostname: If updating rootfs, redirect updates
                                   through this host. Should be None iff
                                   image_url is None.
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
                self.update_via_test_payloads(devserver_hostname, image_url,
                                              stateful_url, clobber=True)
                self._host.reboot()
            except error.AutoservRunError:
                logging.fatal('Error re-imaging the machine with the source '
                              'image %s', image_url)
                raise error.TestError(
                        'Could not update to pre-conditions of test. This is '
                        'most likely a problem with the autotest lab and not '
                        'autoupdate.')


    def stage_artifacts_onto_devserver(self, autotest_devserver, test_conf):
        """Stages artifacts that will be used by the test onto the devserver.

        @param autotest_devserver: instance of client.common_lib.dev_server to
                                   use to reach the devserver instance for this
                                   build.
        @param test_conf: a dictionary containing test configuration values

        @return a _STAGED_URLS tuple containing the staged urls.
        """
        logging.info('Staging images onto autotest devserver (%s)',
                     autotest_devserver.url())

        source_image_uri = test_conf['source_image_uri']

        staged_source_url = None
        source_stateful_uri = None
        staged_source_stateful_url = None
        if self._use_servo:
            staged_source_url = self._stage_image(
                    autotest_devserver, source_image_uri)
            # Test image already contains a stateful update, leave
            # staged_source_stateful_url untouhced.
        else:
            staged_source_url = self._stage_payload_by_uri(
                    autotest_devserver, source_image_uri)

            # In order to properly install the source image using a full
            # payload we'll also need the stateful update that comes with it.
            # In general, tests may have their source artifacts in a different
            # location than their payloads. This is determined by whether or
            # not the source_archive_uri attribute is set; if it isn't set,
            # then we derive it from the dirname of the source payload.
            source_archive_uri = test_conf.get('source_archive_uri')
            if source_archive_uri:
                source_stateful_uri = self._get_stateful_uri(source_archive_uri)
            else:
                source_stateful_uri = self._payload_to_stateful_uri(
                        source_image_uri)

            staged_source_stateful_url = self._stage_payload_by_uri(
                    autotest_devserver, source_stateful_uri)

        target_payload_uri = test_conf['target_payload_uri']
        staged_target_url = self._stage_payload_by_uri(
                autotest_devserver, target_payload_uri)
        target_stateful_uri = None
        target_archive_uri = test_conf.get('target_archive_uri')
        if not target_archive_uri and self._job_repo_url:
            _, devserver_label = tools.get_devserver_build_from_package_url(
                    self._job_repo_url)
            staged_target_stateful_url = self._stage_payload(
                    autotest_devserver, devserver_label,
                    self._STATEFUL_UPDATE_FILENAME)
        else:
            if target_archive_uri:
                target_stateful_uri = self._get_stateful_uri(target_archive_uri)
            else:
                target_stateful_uri = self._payload_to_stateful_uri(
                    target_payload_uri)

            staged_target_stateful_url = self._stage_payload_by_uri(
                    autotest_devserver, target_stateful_uri)

        # Log all the urls.
        logging.info('Source %s from %s staged at %s',
                     'image' if self._use_servo else 'full payload',
                     source_image_uri, staged_source_url)
        if staged_source_stateful_url:
            logging.info('Source stateful update from %s staged at %s',
                         source_stateful_uri, staged_source_stateful_url)
        logging.info('%s test payload from %s staged at %s',
                     test_conf['update_type'], target_payload_uri,
                     staged_target_url)
        logging.info('Target stateful update from %s staged at %s',
                     target_stateful_uri or 'standard location',
                     staged_target_stateful_url)

        return self._STAGED_URLS(staged_source_url, staged_source_stateful_url,
                                 staged_target_url, staged_target_stateful_url)


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
                    'Path to devserver source tree not provided; please define '
                    'devserver_dir under [CROS] in your shadow_config.ini')


    def cleanup(self):
        """Kill the omaha devserver if it's still around."""
        if self._omaha_devserver:
            self._omaha_devserver.stop_devserver()

        self._omaha_devserver = None


    def _verify_preconditions(self):
        """Validate input args make sense."""
        if self._use_servo and not self._host.servo:
            raise error.AutotestError('Servo use specified but no servo '
                                      'attached to host object.')

        if not self._use_test_image and not self._use_servo:
            raise error.TestError('Cannot install mp image without servo.')


    def _dump_update_engine_log(self):
        """Dumps relevant AU error log."""
        if not self._use_servo:
            logging.error('Test failed -- dumping snippet of update_engine log')
            try:
                error_log = self._host.run_output(
                        'tail -n 40 /var/log/update_engine.log')
                logging.error(error_log)
            except Exception:
                # Mute any exceptions we get printing debug logs.
                pass


    def run_update_test(self, staged_urls, test_conf):
        """Runs the actual update test once preconditions are met.

        @param staged_urls: A _STAGED_URLS tuple containing the staged urls.
        @param test_conf: A dictionary containing test configuration values

        @raises ExpectedUpdateEventChainFailed if we failed to verify an update
                event.
        """
        # On test images, record the active root partition.
        source_rootfs_partition = None
        if self._use_test_image:
            source_rootfs_partition = self._get_rootdev()
            logging.info('Source image rootfs partition: %s',
                         source_rootfs_partition)

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
        logging.info('Polling update progress from omaha/devserver: %s',
                     omaha_hostlog_url)
        log_verifier = UpdateEventLogVerifier(
                omaha_hostlog_url,
                self._DEVSERVER_HOSTLOG_REQUEST_TIMEOUT_SECONDS)

        # Verify chain of events in a successful update process.
        chain = ExpectedUpdateEventChain(
                (self._WAIT_FOR_INITIAL_UPDATE_CHECK_SECONDS,
                 ExpectedUpdateEvent(
                     version=test_conf['source_release'],
                     error_message=('Failed to receive initial update check. '
                                    'Check Omaha devserver log in this '
                                    'output.'))),
                (self._WAIT_FOR_DOWNLOAD_STARTED_SECONDS,
                 ExpectedUpdateEvent(
                     event_type=EVENT_TYPE_DOWNLOAD_STARTED,
                     event_result=EVENT_RESULT_SUCCESS,
                     version=test_conf['source_release'],
                     error_message=(
                             'Failed to start the download of the update '
                             'payload from the staging server. Check both the '
                             'omaha log and update_engine.log in sysinfo (or '
                             'on the DUT).'))),
                (self._WAIT_FOR_DOWNLOAD_COMPLETED_SECONDS,
                 ExpectedUpdateEvent(
                     event_type=EVENT_TYPE_DOWNLOAD_FINISHED,
                     event_result=EVENT_RESULT_SUCCESS,
                     version=test_conf['source_release'],
                     error_message=(
                             'Failed to finish download from devserver. Check '
                             'the update_engine.log in sysinfo (or on the '
                             'DUT).'))),
                (self._WAIT_FOR_UPDATE_COMPLETED_SECONDS,
                 ExpectedUpdateEvent(
                     event_type=EVENT_TYPE_UPDATE_COMPLETE,
                     event_result=EVENT_RESULT_SUCCESS,
                     version=test_conf['source_release'],
                     error_message=(
                             'Failed to complete update before reboot. Check '
                             'the update_engine.log in sysinfo (or on the '
                             'DUT).'))))

        log_verifier.verify_expected_event_chain(chain)

        # Wait after an update completion (safety margin).
        _wait(self._WAIT_AFTER_UPDATE_SECONDS, 'after update completion')

        # Reboot the DUT after the update.
        if self._use_servo:
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
                     event_type=EVENT_TYPE_UPDATE_COMPLETE,
                     event_result=EVENT_RESULT_SUCCESS_REBOOT,
                     version=test_conf['target_release'],
                     previous_version=test_conf['source_release'],
                     error_message=(
                             'Failed to reboot into the target version after '
                             'an update. Check the sysinfo logs. This probably '
                             'means that the updated image failed to verify '
                             'after reboot and might mean that the update '
                             'payload is bad'))))

        log_verifier.verify_expected_event_chain(chain)

        # On test images, make sure we're using a different partition after
        # the update.
        if self._use_test_image:
            target_rootfs_partition = self._get_rootdev()
            if target_rootfs_partition == source_rootfs_partition:
                raise error.TestFail(
                        'Rootfs partition did not change (%s)' %
                        target_rootfs_partition)

            logging.info(
                    'Target image rootfs partition changed as expected: %s',
                    target_rootfs_partition)

        logging.info('Update successful, test completed')


    def run_once(self, host, test_conf, use_servo):
        """Performs a complete auto update test.

        @param host: a host object representing the DUT
        @param test_conf: a dictionary containing test configuration values
        @param use_servo: True whether we should use servo.

        @raise error.TestError if anything went wrong with setting up the test;
               error.TestFail if any part of the test has failed.

        """

        if not test_conf['target_release']:
            raise RequiredArgumentMissing(
                    'target_release is a required argument.')

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

        # Find a devserver to use. We use the payload URI as argument for the
        # lab's devserver load-balancing mechanism.
        autotest_devserver = dev_server.ImageServer.resolve(
                test_conf['target_payload_uri'])
        devserver_hostname = urlparse.urlparse(
                autotest_devserver.url()).hostname

        # Stage source images and update payloads onto a devserver.
        staged_urls = self.stage_artifacts_onto_devserver(
                autotest_devserver, test_conf)

        # Install the source version onto the DUT.
        self.install_source_version(devserver_hostname,
                                    staged_urls.source_url,
                                    staged_urls.source_stateful_url)

        self._omaha_devserver = OmahaDevserver(
                devserver_hostname, self._devserver_dir, staged_urls.target_url)
        self._omaha_devserver.start_devserver()
        try:
            self.run_update_test(staged_urls, test_conf)
        except ExpectedUpdateEventChainFailed:
            self._dump_update_engine_log()
            raise

        # Only do login tests with recent builds, since they depend on
        # some binary compatibility with the build itself.
        # '5116.0.0' -> ('5116', '0', '0') -> 5116
        if int(test_conf['target_release'].split('.')[0]) > 5110:
            # Login, to prove we can after the update.
            logging.info('Attempting to login to verify image.')

            client_at = autotest.Autotest(self._host)
            client_at.run_test('login_LoginSuccess')
        else:
            logging.info('Not attempting login test.')
