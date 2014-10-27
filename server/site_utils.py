# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import httplib
import json
import logging
import os
import random
import re
import time
import urllib2

import common
from autotest_lib.client.common_lib import base_utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import job_status


_SHERIFF_JS = global_config.global_config.get_config_value(
    'NOTIFICATIONS', 'sheriffs', default='')
_LAB_SHERIFF_JS = global_config.global_config.get_config_value(
    'NOTIFICATIONS', 'lab_sheriffs', default='')
_CHROMIUM_BUILD_URL = global_config.global_config.get_config_value(
    'NOTIFICATIONS', 'chromium_build_url', default='')

LAB_GOOD_STATES = ('open', 'throttled')


class TestLabException(Exception):
    """Exception raised when the Test Lab blocks a test or suite."""
    pass


class ParseBuildNameException(Exception):
    """Raised when ParseBuildName() cannot parse a build name."""
    pass


def ParseBuildName(name):
    """Format a build name, given board, type, milestone, and manifest num.

    @param name: a build name, e.g. 'x86-alex-release/R20-2015.0.0' or a
                 relative build name, e.g. 'x86-alex-release/LATEST'

    @return board: board the manifest is for, e.g. x86-alex.
    @return type: one of 'release', 'factory', or 'firmware'
    @return milestone: (numeric) milestone the manifest was associated with.
                        Will be None for relative build names.
    @return manifest: manifest number, e.g. '2015.0.0'.
                      Will be None for relative build names.

    """
    match = re.match(r'(trybot-)?(?P<board>[\w-]+)-(?P<type>\w+)/'
                     r'(R(?P<milestone>\d+)-(?P<manifest>[\d.ab-]+)|LATEST)',
                     name)
    if match and len(match.groups()) >= 5:
        return (match.group('board'), match.group('type'),
                match.group('milestone'), match.group('manifest'))
    raise ParseBuildNameException('%s is a malformed build name.' % name)


def get_label_from_afe(hostname, label_prefix, afe):
    """Retrieve a host's specific label from the AFE.

    Looks for a host label that has the form <label_prefix>:<value>
    and returns the "<value>" part of the label. None is returned
    if there is not a label matching the pattern

    @param hostname: hostname of given DUT.
    @param label_prefix: prefix of label to be matched, e.g., |board:|
    @param afe: afe instance.
    @returns the label that matches the prefix or 'None'

    """
    labels = afe.get_labels(name__startswith=label_prefix,
                            host__hostname__in=[hostname])
    if labels and len(labels) == 1:
        return labels[0].name.split(label_prefix, 1)[1]


def get_board_from_afe(hostname, afe):
    """Retrieve given host's board from its labels in the AFE.

    Looks for a host label of the form "board:<board>", and
    returns the "<board>" part of the label.  `None` is returned
    if there is not a single, unique label matching the pattern.

    @param hostname: hostname of given DUT.
    @param afe: afe instance.
    @returns board from label, or `None`.

    """
    return get_label_from_afe(hostname, constants.BOARD_PREFIX, afe)


def get_build_from_afe(hostname, afe):
    """Retrieve the current build for given host from the AFE.

    Looks through the host's labels in the AFE to determine its build.

    @param hostname: hostname of given DUT.
    @param afe: afe instance.
    @returns The current build or None if it could not find it or if there
             were multiple build labels assigned to this host.

    """
    return get_label_from_afe(hostname, constants.VERSION_PREFIX, afe)


def get_sheriffs(lab_only=False):
    """
    Polls the javascript file that holds the identity of the sheriff and
    parses it's output to return a list of chromium sheriff email addresses.
    The javascript file can contain the ldap of more than one sheriff, eg:
    document.write('sheriff_one, sheriff_two').

    @param lab_only: if True, only pulls lab sheriff.
    @return: A list of chroium.org sheriff email addresses to cc on the bug.
             An empty list if failed to parse the javascript.
    """
    sheriff_ids = []
    sheriff_js_list = _LAB_SHERIFF_JS.split(',')
    if not lab_only:
        sheriff_js_list.extend(_SHERIFF_JS.split(','))

    for sheriff_js in sheriff_js_list:
        try:
            url_content = base_utils.urlopen('%s%s'% (
                _CHROMIUM_BUILD_URL, sheriff_js)).read()
        except (ValueError, IOError) as e:
            logging.warning('could not parse sheriff from url %s%s: %s',
                             _CHROMIUM_BUILD_URL, sheriff_js, str(e))
        except (urllib2.URLError, httplib.HTTPException) as e:
            logging.warning('unexpected error reading from url "%s%s": %s',
                             _CHROMIUM_BUILD_URL, sheriff_js, str(e))
        else:
            ldaps = re.search(r"document.write\('(.*)'\)", url_content)
            if not ldaps:
                logging.warning('Could not retrieve sheriff ldaps for: %s',
                                 url_content)
                continue
            sheriff_ids += ['%s@chromium.org' % alias.replace(' ', '')
                            for alias in ldaps.group(1).split(',')]
    return sheriff_ids


def remote_wget(source_url, dest_path, ssh_cmd):
    """wget source_url from localhost to dest_path on remote host using ssh.

    @param source_url: The complete url of the source of the package to send.
    @param dest_path: The path on the remote host's file system where we would
        like to store the package.
    @param ssh_cmd: The ssh command to use in performing the remote wget.
    """
    wget_cmd = ("wget -O - %s | %s 'cat >%s'" %
                (source_url, ssh_cmd, dest_path))
    base_utils.run(wget_cmd)


_MAX_LAB_STATUS_ATTEMPTS = 5
def _get_lab_status(status_url):
    """Grabs the current lab status and message.

    @returns The JSON object obtained from the given URL.

    """
    retry_waittime = 1
    for _ in range(_MAX_LAB_STATUS_ATTEMPTS):
        try:
            response = urllib2.urlopen(status_url)
        except IOError as e:
            logging.debug('Error occurred when grabbing the lab status: %s.',
                          e)
            time.sleep(retry_waittime)
            continue
        # Check for successful response code.
        if response.getcode() == 200:
            return json.load(response)
        time.sleep(retry_waittime)
    return None


def _decode_lab_status(lab_status, build):
    """Decode lab status, and report exceptions as needed.

    Take a deserialized JSON object from the lab status page, and
    interpret it to determine the actual lab status.  Raise
    exceptions as required to report when the lab is down.

    @param build: build name that we want to check the status of.

    @raises TestLabException Raised if a request to test for the given
                             status and build should be blocked.
    """
    # First check if the lab is up.
    if not lab_status['general_state'] in LAB_GOOD_STATES:
        raise TestLabException('Chromium OS Test Lab is closed: '
                               '%s.' % lab_status['message'])

    # Check if the build we wish to use is disabled.
    # Lab messages should be in the format of:
    #    Lab is 'status' [regex ...] (comment)
    # If the build name matches any regex, it will be blocked.
    build_exceptions = re.search('\[(.*)\]', lab_status['message'])
    if not build_exceptions or not build:
        return
    for build_pattern in build_exceptions.group(1).split():
        if re.search(build_pattern, build):
            raise TestLabException('Chromium OS Test Lab is closed: '
                                   '%s matches %s.' % (
                                           build, build_pattern))
    return


def is_in_lab():
    """Check if current Autotest instance is in lab

    @return: True if the Autotest instance is in lab.
    """
    test_server_name = global_config.global_config.get_config_value(
              'SERVER', 'hostname')
    return test_server_name.startswith('cautotest')


def check_lab_status(build):
    """Check if the lab status allows us to schedule for a build.

    Checks if the lab is down, or if testing for the requested build
    should be blocked.

    @param build: Name of the build to be scheduled for testing.

    @raises TestLabException Raised if a request to test for the given
                             status and build should be blocked.

    """
    # Ensure we are trying to schedule on the actual lab.
    if not is_in_lab():
        return

    # Download the lab status from its home on the web.
    status_url = global_config.global_config.get_config_value(
            'CROS', 'lab_status_url')
    json_status = _get_lab_status(status_url)
    if json_status is None:
        # We go ahead and say the lab is open if we can't get the status.
        logging.warning('Could not get a status from %s', status_url)
        return
    _decode_lab_status(json_status, build)


def lock_host_with_labels(afe, lock_manager, labels):
    """Lookup and lock one host that matches the list of input labels.

    @param afe: An instance of the afe class, as defined in server.frontend.
    @param lock_manager: A lock manager capable of locking hosts, eg the
        one defined in server.cros.host_lock_manager.
    @param labels: A list of labels to look for on hosts.

    @return: The hostname of a host matching all labels, and locked through the
        lock_manager. The hostname will be as specified in the database the afe
        object is associated with, i.e if it exists in afe_hosts with a .cros
        suffix, the hostname returned will contain a .cros suffix.

    @raises: error.NoEligibleHostException: If no hosts matching the list of
        input labels are available.
    @raises: error.TestError: If unable to lock a host matching the labels.
    """
    potential_hosts = afe.get_hosts(multiple_labels=labels)
    if not potential_hosts:
        raise error.NoEligibleHostException(
                'No devices found with labels %s.' % labels)

    # This prevents errors where a fault might seem repeatable
    # because we lock, say, the same packet capturer for each test run.
    random.shuffle(potential_hosts)
    for host in potential_hosts:
        if lock_manager.lock([host.hostname]):
            logging.info('Locked device %s with labels %s.',
                         host.hostname, labels)
            return host.hostname
        else:
            logging.info('Unable to lock device %s with labels %s.',
                         host.hostname, labels)

    raise error.TestError('Could not lock a device with labels %s' % labels)


def get_test_views_from_tko(suite_job_id, tko):
    """Get test name and result for given suite job ID.

    @param suite_job_id: ID of suite job.
    @param tko: an instance of TKO as defined in server/frontend.py.
    @return: A dictionary of test status keyed by test name, e.g.,
             {'dummy_Fail.Error': 'ERROR', 'dummy_Fail.NAError': 'TEST_NA'}
    @raise: Exception when there is no test view found.

    """
    views = tko.run('get_detailed_test_views', afe_job_id=suite_job_id)
    relevant_views = filter(job_status.view_is_relevant, views)
    if not relevant_views:
        raise Exception('Failed to retrieve job results.')

    test_views = {}
    for view in relevant_views:
        test_views[view['test_name']] = view['status']

    return test_views


def parse_simple_config(config_file):
    """Get paths by parsing a simple config file.

    Each line of the config file is a path for a file or directory.
    Ignore an empty line and a line starting with a hash character ('#').
    One example of this kind of simple config file is
    client/common_lib/logs_to_collect.

    @param config_file: Config file path
    @return: A list of directory strings
    """
    dirs = []
    for l in open(config_file):
        l = l.strip()
        if l and not l.startswith('#'):
            dirs.append(l)
    return dirs


def concat_path_except_last(base, sub):
    """Concatenate two paths but exclude last entry.

    Take two paths as parameters and return a path string in which
    the second path becomes under the first path.
    In addition, remove the last path entry from the concatenated path.
    This works even when two paths are absolute paths.

    e.g., /usr/local/autotest/results/ + /var/log/ =
    /usr/local/autotest/results/var

    e.g., /usr/local/autotest/results/ + /var/log/syslog =
    /usr/local/autotest/results/var/log

    @param base: Beginning path
    @param sub: The path that is concatenated to base
    @return: Concatenated path string
    """
    dirname = os.path.dirname(sub.rstrip('/'))
    return os.path.join(base, dirname.strip('/'))
