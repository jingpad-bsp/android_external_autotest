# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta
import collections
import json
import logging
import os
import urlparse

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server import test
from autotest_lib.server.cros.update_engine import chromiumos_test_platform

def snippet(text):
    """Returns the text with start/end snip markers around it.

    @param text: The snippet text.

    @return The text with start/end snip markers around it.
    """
    snip = '---8<---' * 10
    start = '-- START -'
    end = '-- END -'
    return ('%s%s\n%s\n%s%s' %
            (start, snip[len(start):], text, end, snip[len(end):]))



# Update event types.
EVENT_TYPE_DOWNLOAD_COMPLETE = '1'
EVENT_TYPE_INSTALL_COMPLETE = '2'
EVENT_TYPE_UPDATE_COMPLETE = '3'
EVENT_TYPE_DOWNLOAD_STARTED = '13'
EVENT_TYPE_DOWNLOAD_FINISHED = '14'
EVENT_TYPE_REBOOTED_AFTER_UPDATE = '54'

# Update event results.
EVENT_RESULT_ERROR = '0'
EVENT_RESULT_SUCCESS = '1'
EVENT_RESULT_UPDATE_DEFERRED = '9'

# Omaha event types/results, from update_engine/omaha_request_action.h
# These are stored in dict form in order to easily print out the keys.
EVENT_TYPE_DICT = {
        EVENT_TYPE_DOWNLOAD_COMPLETE: 'download_complete',
        EVENT_TYPE_INSTALL_COMPLETE: 'install_complete',
        EVENT_TYPE_UPDATE_COMPLETE: 'update_complete',
        EVENT_TYPE_DOWNLOAD_STARTED: 'download_started',
        EVENT_TYPE_DOWNLOAD_FINISHED: 'download_finished',
        EVENT_TYPE_REBOOTED_AFTER_UPDATE: 'rebooted_after_update'
}

EVENT_RESULT_DICT = {
        EVENT_RESULT_ERROR: 'error',
        EVENT_RESULT_SUCCESS: 'success',
        EVENT_RESULT_UPDATE_DEFERRED: 'update_deferred'
}


class ExpectedUpdateEventChainFailed(error.TestFail):
    """Raised if we fail to receive an expected event in a chain."""


class ExpectedUpdateEvent(object):
    """Defines an expected event in an update process."""

    _ATTR_NAME_DICT_MAP = {
            'event_type': EVENT_TYPE_DICT,
            'event_result': EVENT_RESULT_DICT,
    }

    _VALID_TYPES = set(EVENT_TYPE_DICT.keys())
    _VALID_RESULTS = set(EVENT_RESULT_DICT.keys())

    def __init__(self, event_type=None, event_result=None, version=None,
                 previous_version=None, on_error=None):
        """Initializes an event expectation.

        @param event_type: Expected event type.
        @param event_result: Expected event result code.
        @param version: Expected reported image version.
        @param previous_version: Expected reported previous image version.
        @param on_error: This is either an object to be returned when a received
                         event mismatches the expectation, or a callable used
                         for generating one. In the latter case, takes as
                         input two attribute dictionaries (expected and actual)
                         and an iterable of mismatched keys. If None, a generic
                         message is returned.
        """
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
        self._on_error = on_error


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


    def _attrs_to_str(self, attrs_dict):
        return ' '.join(['%s=%s' %
                         self._attr_name_and_values(attr_name, attr_val)[0:2]
                         for attr_name, attr_val in attrs_dict.iteritems()])


    def __str__(self):
        return self._attrs_to_str(self._expected_attrs)


    def verify(self, actual_event):
        """Verify the attributes of an actual event.

        @param actual_event: a dictionary containing event attributes

        @return An error message, or None if all attributes as expected.

        """
        mismatched_attrs = [
            attr_name for attr_name, expected_attr_val
            in self._expected_attrs.iteritems()
            if (expected_attr_val and
                not self._verify_attr(attr_name, expected_attr_val,
                                      actual_event.get(attr_name)))]
        if not mismatched_attrs:
            return None
        if callable(self._on_error):
            return self._on_error(self._expected_attrs, actual_event,
                                  mismatched_attrs)
        if self._on_error is None:
            return ('Received event (%s) does not match expectation (%s)' %
                    (self._attrs_to_str(actual_event), self))
        return self._on_error


    def _verify_attr(self, attr_name, expected_attr_val, actual_attr_val):
        """Verifies that an actual log event attributes matches expected on.

        @param attr_name: name of the attribute to verify
        @param expected_attr_val: expected attribute value
        @param actual_attr_val: actual attribute value

        @return True if actual value is present and matches, False otherwise.

        """
        # None values are assumed to be missing and non-matching.
        if actual_attr_val is None:
            logging.error('No value found for %s (expected %s)',
                          *self._attr_name_and_values(attr_name,
                                                      expected_attr_val)[0:2])
            return False

        # We allow expected version numbers (e.g. 2940.0.0) to be contained in
        # actual values (2940.0.0-a1); this is necessary for the test to pass
        # with developer / non-release images.
        if (actual_attr_val == expected_attr_val or
            ('version' in attr_name and expected_attr_val in actual_attr_val)):
            return True

        return False


    def get_attrs(self):
        """Returns a dictionary of expected attributes."""
        return dict(self._expected_attrs)


class ExpectedUpdateEventChain(object):
    """Defines a chain of expected update events."""
    def __init__(self):
        self._expected_event_chain = []
        self._current_timestamp = None


    def add_event(self, expected_event, timeout, on_timeout=None):
        """Adds an expected event to the chain.

        @param expected_event: The event to add.
        @param timeout: A timeout (in seconds) to wait for the event.
        @param on_timeout: An error string to use if the event times out. If
                           None, a generic message is used.
        """
        self._expected_event_chain.append((expected_event, timeout, on_timeout))


    @staticmethod
    def _format_event_with_timeout(expected_event, timeout):
        """Returns a string representation of the event, with timeout."""
        until = 'within %s seconds' % timeout if timeout else 'indefinitely'
        return '%s %s' % (expected_event, until)


    def __str__(self):
        return ('[%s]' %
                ', '.join(
                    [self._format_event_with_timeout(expected_event, timeout)
                     for expected_event, timeout, _
                     in self._expected_event_chain]))


    def __repr__(self):
        return str(self._expected_event_chain)


    def verify(self, get_next_event):
        """Verifies that an actual stream of events complies.

        @param get_next_event: a function returning the next event

        @raises ExpectedUpdateEventChainFailed if we failed to verify an event.

        """
        for expected_event, timeout, on_timeout in self._expected_event_chain:
            logging.info('Expecting %s',
                         self._format_event_with_timeout(expected_event,
                                                         timeout))
            err_msg = self._verify_event_with_timeout(
                    expected_event, timeout, on_timeout, get_next_event)
            if err_msg is not None:
                logging.error('Failed expected event: %s', err_msg)
                raise ExpectedUpdateEventChainFailed(err_msg)


    def _verify_event_with_timeout(self, expected_event, timeout, on_timeout,
                                   get_next_event):
        """Verify an expected event occurs within a given timeout.

        @param expected_event: an expected event
        @param timeout: specified in seconds
        @param on_timeout: A string to return if timeout occurs, or None.
        @param get_next_event: function returning the next event in a stream

        @return None if event complies, an error string otherwise.

        """
        new_event = get_next_event()
        if new_event:
            # If this is the first event, set it as the current time
            if self._current_timestamp is None:
                self._current_timestamp = datetime.strptime(new_event[
                                                                'timestamp'],
                                                            '%Y-%m-%d %H:%M:%S')

            # Get the time stamp for the current event and convert to datetime
            timestamp = new_event['timestamp']
            event_timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

            # Add the timeout onto the timestamp to get its expiry
            event_timeout = self._current_timestamp + timedelta(seconds=timeout)

            # If the event happened before the timeout
            if event_timestamp < event_timeout:
                difference = event_timestamp - self._current_timestamp
                logging.info('Event took %s seconds to fire during the '
                             'update', difference.seconds)
                results = expected_event.verify(new_event)
                self._current_timestamp = event_timestamp
                return results

        logging.error('Timeout expired')
        if on_timeout is None:
            return ('Waiting for event %s timed out after %d seconds' %
                    (expected_event, timeout))
        return on_timeout


class UpdateEventLogVerifier(object):
    """Verifies update event chains on a devserver update log."""
    def __init__(self, event_log_filename):
        self._event_log_filename = event_log_filename
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

        Uses the filename handed to it during initialization to read the
        host log from devserver used during the update.

        @return The next new event in the host log, as reported by devserver;
                None if no such event was found or an error occurred.

        """
        # (Re)read event log from hostlog file, if necessary.
        if len(self._event_log) <= self._num_consumed_events:
            try:
                with open(self._event_log_filename, 'r') as out_log:
                  self._event_log = json.loads(out_log.read())
            except Exception as e:
                raise error.TestFail('Error while reading the hostlogs '
                                     'from devserver: %s' % e)

        # Return next new event, if one is found.
        if len(self._event_log) > self._num_consumed_events:
            new_event = {
                    key: str(val) for key, val
                    in self._event_log[self._num_consumed_events].iteritems()
            }
            self._num_consumed_events += 1
            logging.info('Consumed new event: %s', new_event)
            return new_event


class autoupdate_EndToEndTest(test.test):
    """Complete update test between two Chrome OS releases.

    Performs an end-to-end test of updating a ChromeOS device from one version
    to another. The test performs the following steps:

      1. Stages the source (full) and target update payload on the central
         devserver.
      2. Installs a source image on the DUT (if provided) and reboots to it.
      3. Then starts the target update by calling cros_au RPC on the devserver.
      4. This copies the devserver code and all payloads to the DUT.
      5. Starts a devserver on the DUT.
      6. Starts an update pointing to this local devserver.
      7. Watches as the DUT applies the update to rootfs and stateful.
      8. Reboots and repeats steps 5-6, ensuring that the next update check
         shows the new image version.
      9. Returns the hostlogs collected during each update check for
         verification against expected update events.

    Some notes on naming:
      devserver: Refers to a machine running the Chrome OS Update Devserver.
      autotest_devserver: An autotest wrapper to interact with a devserver.
                          Can be used to stage artifacts to a devserver. While
                          this can also be used to update a machine, we do not
                          use it for that purpose in this test as we manage
                          updates with out own devserver instances (see below).
      *staged_url's: In this case staged refers to the fact that these items
                     are available to be downloaded statically from these urls
                     e.g. 'localhost:8080/static/my_file.gz'. These are usually
                     given after staging an artifact using a autotest_devserver
                     though they can be re-created given enough assumptions.
    """
    version = 1

    # Timeout periods, given in seconds.
    _WAIT_FOR_INITIAL_UPDATE_CHECK_SECONDS = 12 * 60
    # TODO(sosa): Investigate why this needs to be so long (this used to be
    # 120 and regressed).
    _WAIT_FOR_DOWNLOAD_STARTED_SECONDS = 4 * 60
    # See https://crbug.com/731214 before changing WAIT_FOR_DOWNLOAD
    _WAIT_FOR_DOWNLOAD_COMPLETED_SECONDS = 20 * 60
    _WAIT_FOR_UPDATE_COMPLETED_SECONDS = 4 * 60
    _WAIT_FOR_UPDATE_CHECK_AFTER_REBOOT_SECONDS = 15 * 60

    _DEVSERVER_HOSTLOG_ROOTFS = 'devserver_hostlog_rootfs'
    _DEVSERVER_HOSTLOG_REBOOT = 'devserver_hostlog_reboot'

    # Logs and their whereabouts.
    _WHERE_UPDATE_LOG = ('update_engine log (in sysinfo or on the DUT, also '
                         'included in the test log)')

    StagedURLs = collections.namedtuple('StagedURLs', ['source_url',
                                                       'source_stateful_url',
                                                       'target_url',
                                                       'target_stateful_url'])

    def initialize(self):
        """Sets up variables that will be used by test."""
        self._host = None
        self._autotest_devserver = None
        self._source_image_installed = False


    def _get_hostlog_file(self, filename, pid):
        """Return the hostlog file location.

        @param filename: The partial filename to look for.
        @param pid: The pid of the update.

        """
        hosts = [self._host.hostname, self._host.ip]
        for host in hosts:
            hostlog = '%s_%s_%s' % (filename, host, pid)
            file_url = os.path.join(self.job.resultdir,
                                    dev_server.AUTO_UPDATE_LOG_DIR,
                                    hostlog)
            if os.path.exists(file_url):
                return file_url
        raise error.TestFail('Could not find %s for pid %s' % (filename, pid))


    def _dump_update_engine_log(self, test_platform):
        """Dumps relevant AU error log."""
        try:
            error_log = test_platform.get_update_log(80)
            logging.error('Dumping snippet of update_engine log:\n%s',
                          snippet(error_log))
        except Exception:
            # Mute any exceptions we get printing debug logs.
            pass


    def _report_perf_data(self, perf_file):
        """Reports performance and resource data.

        Currently, performance attributes are expected to include 'rss_peak'
        (peak memory usage in bytes).

        @param perf_file: A file with performance metrics.
        """
        logging.debug('Reading perf results from %s.' % perf_file)
        try:
            with open(perf_file, 'r') as perf_file_handle:
                perf_data = json.loads(perf_file_handle.read())
        except Exception as e:
            logging.warning('Error while reading the perf data file: %s' % e)
            return

        rss_peak = perf_data.get('rss_peak')
        if rss_peak:
            rss_peak_kib = rss_peak / 1024
            logging.info('Peak memory (RSS) usage on DUT: %d KiB', rss_peak_kib)
            self.output_perf_value(description='mem_usage_peak',
                                   value=int(rss_peak_kib),
                                   units='KiB',
                                   higher_is_better=False)
        else:
            logging.warning('No rss_peak key in JSON returned by update '
                            'engine perf script.')


    def _error_initial_check(self, expected, actual, mismatched_attrs):
        err_msg = ('The update appears to have completed successfully but '
                   'we found a problem while verifying the hostlog of events '
                   'returned from the update. Some attributes reported for '
                   'the initial update check event are not what we expected: '
                   '%s. ' % mismatched_attrs)
        if 'version' in mismatched_attrs:
            err_msg += ('The expected version is (%s) but reported version was '
                        '(%s). ' % (expected['version'], actual['version']))
            if self._source_image_installed:
                err_msg += ('The source payload we installed was probably '
                            'incorrect or corrupt. ')
            else:
                err_msg += ('The DUT was probably not running the correct '
                            'source image. ')

        err_msg += ('Check the full hostlog for this update in the %s file in '
                    'the %s directory.' % (self._DEVSERVER_HOSTLOG_ROOTFS,
                                           dev_server.AUTO_UPDATE_LOG_DIR))
        return err_msg


    def _error_intermediate(self, expected, actual, mismatched_attrs, action,
                            problem):
        if 'event_result' in mismatched_attrs:
            event_result = actual.get('event_result')
            reported = (('different than expected (%s)' %
                         EVENT_RESULT_DICT[event_result])
                        if event_result else 'missing')
            return ('The updater reported result code is %s. This could be an '
                    'updater bug or a connectivity problem; check the %s.' %
                    (reported, self._WHERE_UPDATE_LOG))
        if 'event_type' in mismatched_attrs:
            event_type = actual.get('event_type')
            reported = ('different (%s)' % EVENT_TYPE_DICT[event_type]
                        if event_type else 'missing')
            return ('Expected the updater to %s (%s) but received event type '
                    'is %s. This could be an updater %s; check the %s.' %
                    (action, EVENT_TYPE_DICT[expected['event_type']], reported,
                     problem, self._WHERE_UPDATE_LOG))
        if 'version' in mismatched_attrs:
            return ('The updater reported an unexpected version despite '
                    'previously reporting the correct one. This is most likely '
                    'a bug in update engine; check the %s.' %
                    self._WHERE_UPDATE_LOG)

        return 'A test bug occurred; inspect the test log.'


    def _error_download_started(self, expected, actual, mismatched_attrs):
        return self._error_intermediate(expected, actual, mismatched_attrs,
                                        'begin downloading',
                                        'bug, crash or provisioning error')


    def _error_download_finished(self, expected, actual, mismatched_attrs):
        return self._error_intermediate(expected, actual, mismatched_attrs,
                                        'finish downloading', 'bug or crash')


    def _error_update_complete(self, expected, actual, mismatched_attrs):
        return self._error_intermediate(expected, actual, mismatched_attrs,
                                        'complete the update', 'bug or crash')


    def _error_reboot_after_update(self, expected, actual, mismatched_attrs):
        err_msg = ('The update completed successfully but there was a problem '
                   'with the post-reboot update check. After a successful '
                   'update, we do a final update check to parse a unique '
                   'omaha request. The mistmatched attributes for this update '
                   'check were %s. ' % mismatched_attrs)
        if 'event_result' in mismatched_attrs:
            err_msg += ('The event_result was expected to be (%s:%s) but '
                        'reported (%s:%s). ' %
                            (expected['event_result'],
                             EVENT_RESULT_DICT[expected['event_result']],
                             actual.get('event_result'),
                             EVENT_RESULT_DICT[actual.get('event_result')]))
        if 'event_type' in mismatched_attrs:
            err_msg += ('The event_type was expeted to be (%s:%s) but '
                        'reported (%s:%s). ' %
                            (expected['event_type'],
                             EVENT_TYPE_DICT[expected['event_type']],
                             actual.get('event_type'),
                             EVENT_TYPE_DICT[actual.get('event_type')]))
        if 'version' in mismatched_attrs:
          err_msg += ('The version was expected to be (%s) but '
                      'reported (%s). This probably means that the payload '
                      'we applied was incorrect or corrupt. ' %
                      (expected['version'], actual['version']))
        if 'previous_version' in mismatched_attrs:
            err_msg += ('The previous version is expected to be (%s) but '
                        'reported (%s). This can happen if we retried the '
                        'update after rootfs update completed on the first '
                        'attempt. Or if stateful got wiped and '
                        '/var/lib/update_engine/prefs/previous-version was '
                        'deleted. ' % (expected['previous_version'],
                                       actual['previous_version']))
        err_msg += ('You can see the full hostlog for this update check in '
                    'the %s file within the %s directory. ' %
                    (self._DEVSERVER_HOSTLOG_REBOOT,
                     dev_server.AUTO_UPDATE_LOG_DIR))
        return err_msg


    def _timeout_err(self, desc, timeout, event_type=None):
        if event_type is not None:
            desc += ' (%s)' % EVENT_TYPE_DICT[event_type]
        return ('The update completed successfully but one of the steps of '
                'the update took longer than we would like. We failed to '
                'receive %s within %d seconds.' % (desc, timeout))

    def _stage_payload(self, build_name, filename, archive_url=None):
        """Stage the given payload onto the devserver.

        Works for either a stateful or full/delta test payload. Expects the
        gs_path or a combo of build_name + filename.

        @param build_name: The build name e.g. x86-mario-release/<version>.
                           If set, assumes default gs archive bucket and
                           requires filename to be specified.
        @param filename: In conjunction with build_name, this is the file you
                         are downloading.
        @param archive_url: An optional GS archive location, if not using the
                            devserver's default.

        @return URL of the staged payload on the server.

        @raise error.TestError if there's a problem with staging.

        """
        try:
            self._autotest_devserver.stage_artifacts(image=build_name,
                                                     files=[filename],
                                                     archive_url=archive_url)
            return self._autotest_devserver.get_staged_file_url(filename,
                                                                build_name)
        except dev_server.DevServerException, e:
            raise error.TestError('Failed to stage payload: %s' % e)


    def _stage_payload_by_uri(self, payload_uri):
        """Stage a payload based on its GS URI.

        This infers the build's label, filename and GS archive from the
        provided GS URI.

        @param payload_uri: The full GS URI of the payload.

        @return URL of the staged payload on the server.

        @raise error.TestError if there's a problem with staging.

        """
        archive_url, _, filename = payload_uri.rpartition('/')
        build_name = urlparse.urlsplit(archive_url).path.strip('/')
        return self._stage_payload(build_name, filename,
                                   archive_url=archive_url)


    def _get_stateful_uri(self, build_uri):
        """Returns a complete GS URI of a stateful update given a build path."""
        return '/'.join([build_uri.rstrip('/'), 'stateful.tgz'])


    def _payload_to_stateful_uri(self, payload_uri):
        """Given a payload GS URI, returns the corresponding stateful URI."""
        build_uri = payload_uri.rpartition('/')[0]
        if build_uri.endswith('payloads'):
            build_uri = build_uri.rpartition('/')[0]
        return self._get_stateful_uri(build_uri)


    def _stage_artifacts_onto_devserver(self, test_conf):
        """Stages artifacts that will be used by the test onto the devserver.

        @param test_conf: a dictionary containing test configuration values

        @return a StagedURLs tuple containing the staged urls.
        """
        logging.info('Staging images onto autotest devserver (%s)',
                     self._autotest_devserver.url())

        staged_source_url = None
        source_payload_uri = test_conf['source_payload_uri']

        if source_payload_uri:
            staged_source_url = self._stage_payload_by_uri(source_payload_uri)

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
                    source_payload_uri)

            staged_source_stateful_url = self._stage_payload_by_uri(
                source_stateful_uri)

            # Log source image URLs.
            logging.info('Source full payload from %s staged at %s',
                         source_payload_uri, staged_source_url)
            if staged_source_stateful_url:
                logging.info('Source stateful update from %s staged at %s',
                             source_stateful_uri, staged_source_stateful_url)

        target_payload_uri = test_conf['target_payload_uri']
        staged_target_url = self._stage_payload_by_uri(target_payload_uri)
        staged_target_stateful_url = None
        target_archive_uri = test_conf.get('target_archive_uri')
        if target_archive_uri:
            target_stateful_uri = self._get_stateful_uri(target_archive_uri)
        else:
            target_stateful_uri = self._payload_to_stateful_uri(
                target_payload_uri)

        if not staged_target_stateful_url and target_stateful_uri:
            staged_target_stateful_url = self._stage_payload_by_uri(
                target_stateful_uri)

        # Log target payload URLs.
        logging.info('%s test payload from %s staged at %s',
                     test_conf['update_type'], target_payload_uri,
                     staged_target_url)
        logging.info('Target stateful update from %s staged at %s',
                     target_stateful_uri, staged_target_stateful_url)

        return self.StagedURLs(staged_source_url, staged_source_stateful_url,
                               staged_target_url, staged_target_stateful_url)


    def verify_version(self, expected, actual):
        if expected != actual:
            err_msg = 'Failed to verify OS version. Expected %s, was %s' % (
                expected, actual)
            logging.error(err_msg)
            raise error.TestFail(err_msg)

    def run_update_test(self, cros_device, test_conf):
        """Runs the actual update test once preconditions are met.

        @param test_platform: TestPlatform implementation.
        @param test_conf: A dictionary containing test configuration values

        @raises ExpectedUpdateEventChainFailed if we failed to verify an update
                event.
        """

        # Record the active root partition.
        source_active_slot = cros_device.get_active_slot()
        logging.info('Source active slot: %s', source_active_slot)

        source_release = test_conf['source_release']
        target_release = test_conf['target_release']

        cros_device.copy_perf_script_to_device(self.bindir)
        try:
            # Update the DUT to the target image.
            pid = cros_device.install_target_image(test_conf[
                'target_payload_uri'])

            # Verify the host log that was returned from the update.
            file_url = self._get_hostlog_file(self._DEVSERVER_HOSTLOG_ROOTFS,
                                              pid)

            logging.info('Checking update steps with devserver hostlog file: '
                         '%s' % file_url)
            log_verifier = UpdateEventLogVerifier(file_url)

            # Verify chain of events in a successful update process.
            chain = ExpectedUpdateEventChain()
            chain.add_event(
                    ExpectedUpdateEvent(
                        version=source_release,
                        on_error=self._error_initial_check),
                    self._WAIT_FOR_INITIAL_UPDATE_CHECK_SECONDS,
                    on_timeout=self._timeout_err(
                            'an initial update check',
                            self._WAIT_FOR_INITIAL_UPDATE_CHECK_SECONDS))
            chain.add_event(
                    ExpectedUpdateEvent(
                        event_type=EVENT_TYPE_DOWNLOAD_STARTED,
                        event_result=EVENT_RESULT_SUCCESS,
                        version=source_release,
                        on_error=self._error_download_started),
                    self._WAIT_FOR_DOWNLOAD_STARTED_SECONDS,
                    on_timeout=self._timeout_err(
                            'a download started notification',
                            self._WAIT_FOR_DOWNLOAD_STARTED_SECONDS,
                            event_type=EVENT_TYPE_DOWNLOAD_STARTED))
            chain.add_event(
                    ExpectedUpdateEvent(
                        event_type=EVENT_TYPE_DOWNLOAD_FINISHED,
                        event_result=EVENT_RESULT_SUCCESS,
                        version=source_release,
                        on_error=self._error_download_finished),
                    self._WAIT_FOR_DOWNLOAD_COMPLETED_SECONDS,
                    on_timeout=self._timeout_err(
                            'a download finished notification',
                            self._WAIT_FOR_DOWNLOAD_COMPLETED_SECONDS,
                            event_type=EVENT_TYPE_DOWNLOAD_FINISHED))
            chain.add_event(
                    ExpectedUpdateEvent(
                        event_type=EVENT_TYPE_UPDATE_COMPLETE,
                        event_result=EVENT_RESULT_SUCCESS,
                        version=source_release,
                        on_error=self._error_update_complete),
                    self._WAIT_FOR_UPDATE_COMPLETED_SECONDS,
                    on_timeout=self._timeout_err(
                            'an update complete notification',
                            self._WAIT_FOR_UPDATE_COMPLETED_SECONDS,
                            event_type=EVENT_TYPE_UPDATE_COMPLETE))

            log_verifier.verify_expected_event_chain(chain)

        except:
            logging.fatal('ERROR: Failure occurred during the target update.')
            raise

        perf_file = cros_device.get_perf_stats_for_update(self.job.resultdir)
        if perf_file is not None:
            self._report_perf_data(perf_file)

        if cros_device.oobe_triggers_update():
            # If DUT automatically checks for update during OOBE,
            # checking the post-update CrOS version and slot is sufficient.
            # This command checks the OS version.
            # The slot is checked a little later, after the else block.
            logging.info('Skipping post reboot update check.')
            self.verify_version(target_release, cros_device.get_cros_version())

        else:
            # Observe post-reboot update check, which should indicate that the
            # image version has been updated.
            # Verify the host log that was returned from the update.
            file_url = self._get_hostlog_file(self._DEVSERVER_HOSTLOG_REBOOT,
                                              pid)

            logging.info('Checking post-reboot devserver hostlogs: %s' %
                         file_url)
            log_verifier = UpdateEventLogVerifier(file_url)

            chain = ExpectedUpdateEventChain()
            chain.add_event(
                ExpectedUpdateEvent(
                    event_type=EVENT_TYPE_REBOOTED_AFTER_UPDATE,
                    event_result=EVENT_RESULT_SUCCESS,
                    version=target_release,
                    previous_version=source_release,
                    on_error=self._error_reboot_after_update),
                self._WAIT_FOR_UPDATE_CHECK_AFTER_REBOOT_SECONDS,
                on_timeout=self._timeout_err(
                        'a successful reboot notification',
                        self._WAIT_FOR_UPDATE_CHECK_AFTER_REBOOT_SECONDS,
                        event_type=EVENT_TYPE_UPDATE_COMPLETE))

            log_verifier.verify_expected_event_chain(chain)

        # Make sure we're using a different slot after the update.
        target_active_slot = cros_device.get_active_slot()
        if target_active_slot == source_active_slot:
            err_msg = 'The active image slot did not change after the update.'
            if None in (source_release, target_release):
                err_msg += (' The DUT likely rebooted into the old image, which '
                            'probably means that the payload we applied was '
                            'corrupt. But since we did not check the source '
                            'and/or target version we cannot say for sure.')
            elif source_release == target_release:
                err_msg += (' Given that the source and target versions are '
                            'identical, the DUT likely rebooted into the old '
                            'image. This probably means that the payload we '
                            'applied was corrupt.')
            else:
                err_msg += (' This is strange since the DUT reported the '
                            'correct target version. This is probably a system '
                            'bug; check the DUT system log.')
            raise error.TestFail(err_msg)

        logging.info('Target active slot changed as expected: %s',
                     target_active_slot)

        logging.info('Update successful, test completed')


    def run_once(self, host, test_conf):
        """Performs a complete auto update test.

        @param host: a host object representing the DUT
        @param test_conf: a dictionary containing test configuration values

        @raise error.TestError if anything went wrong with setting up the test;
               error.TestFail if any part of the test has failed.
        """
        self._host = host
        logging.debug('The test configuration supplied: %s', test_conf)

        # Find a devserver to use. We first try to pick a devserver with the
        # least load. In case all devservers' load are higher than threshold,
        # fall back to the old behavior by picking a devserver based on the
        # payload URI, with which ImageServer.resolve will return a random
        # devserver based on the hash of the URI.
        # The picked devserver needs to respect the location of the host if
        # 'prefer_local_devserver' is set to True or 'restricted_subnets' is
        # set.
        hostname = self._host.hostname if self._host else None
        least_loaded_devserver = dev_server.get_least_loaded_devserver(
                hostname=hostname)
        if least_loaded_devserver:
            logging.debug('Choosing the least loaded devserver: %s',
                          least_loaded_devserver)
            self._autotest_devserver = dev_server.ImageServer(
                least_loaded_devserver)
        else:
            logging.warning('No devserver meets the maximum load requirement. '
                            'Picking a random devserver to use.')
            self._autotest_devserver = dev_server.ImageServer.resolve(
                    test_conf['target_payload_uri'], host.hostname)
        devserver_hostname = urlparse.urlparse(
                self._autotest_devserver.url()).hostname

        logging.info('Devserver chosen for this run: %s', devserver_hostname)

        # Stage payloads for source and target onto the devserver.
        staged_urls = self._stage_artifacts_onto_devserver(test_conf)
        self._source_image_installed = bool(staged_urls.source_url)

        # Get an object representing the CrOS DUT.
        cros_device = chromiumos_test_platform.ChromiumOSTestPlatform(
            self._host, self._autotest_devserver, self.job.resultdir)

        cros_device.install_source_image(test_conf['source_payload_uri'])
        cros_device.check_login_after_source_update()

        # Start the update.
        try:
            self.run_update_test(cros_device, test_conf)
        except ExpectedUpdateEventChainFailed:
            self._dump_update_engine_log(cros_device)
            raise

        cros_device.check_login_after_source_update()