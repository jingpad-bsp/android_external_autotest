# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import os
import re
import signal
import socket
import time
import urllib2

from autotest_lib.client.common_lib import base_utils, error, global_config
from autotest_lib.client.cros import constants


# Keep checking if the pid is alive every second until the timeout (in seconds)
CHECK_PID_IS_ALIVE_TIMEOUT = 6



_LOCAL_HOST_LIST = ('localhost', '127.0.0.1')

LAB_GOOD_STATES = ('open', 'throttled')

_SHERIFF_JS = global_config.global_config.get_config_value(
    'NOTIFICATIONS', 'sheriffs', default='')
_CHROMIUM_BUILD_URL = global_config.global_config.get_config_value(
    'NOTIFICATIONS', 'chromium_build_url', default='')


def ping(host, deadline=None, tries=None, timeout=60):
    """Attempt to ping |host|.

    Shell out to 'ping' to try to reach |host| for |timeout| seconds.
    Returns exit code of ping.

    Per 'man ping', if you specify BOTH |deadline| and |tries|, ping only
    returns 0 if we get responses to |tries| pings within |deadline| seconds.

    Specifying |deadline| or |count| alone should return 0 as long as
    some packets receive responses.

    @param host: the host to ping.
    @param deadline: seconds within which |tries| pings must succeed.
    @param tries: number of pings to send.
    @param timeout: number of seconds after which to kill 'ping' command.
    @return exit code of ping command.
    """
    args = [host]
    if deadline:
        args.append('-w%d' % deadline)
    if tries:
        args.append('-c%d' % tries)
    return base_utils.run('ping', args=args,
                          ignore_status=True, timeout=timeout,
                          stdout_tee=base_utils.TEE_TO_LOGS,
                          stderr_tee=base_utils.TEE_TO_LOGS).exit_status


def host_is_in_lab_zone(hostname):
    """Check if the host is in the CROS.dns_zone.

    @param hostname: The hostname to check.
    @returns True if hostname.dns_zone resolves, otherwise False.
    """
    host_parts = hostname.split('.')
    dns_zone = global_config.global_config.get_config_value('CROS', 'dns_zone',
                                                            default=None)
    fqdn = '%s.%s' % (host_parts[0], dns_zone)
    try:
        socket.gethostbyname(fqdn)
        return True
    except socket.gaierror:
      return False


def get_chrome_version(job_views):
    """
    Retrieves the version of the chrome binary associated with a job.

    When a test runs we query the chrome binary for it's version and drop
    that value into a client keyval. To retrieve the chrome version we get all
    the views associated with a test from the db, including those of the
    server and client jobs, and parse the version out of the first test view
    that has it. If we never ran a single test in the suite the job_views
    dictionary will not contain a chrome version.

    This method cannot retrieve the chrome version from a dictionary that
    does not conform to the structure of an autotest tko view.

    @param job_views: a list of a job's result views, as returned by
                      the get_detailed_test_views method in rpc_interface.
    @return: The chrome version string, or None if one can't be found.
    """

    # Aborted jobs have no views.
    if not job_views:
        return None

    for view in job_views:
        if (view.get('attributes')
            and constants.CHROME_VERSION in view['attributes'].keys()):

            return view['attributes'].get(constants.CHROME_VERSION)

    logging.warning('Could not find chrome version for failure.')
    return None


def get_current_board():
    """Return the current board name.

    @return current board name, e.g "lumpy", None on fail.
    """
    with open('/etc/lsb-release') as lsb_release_file:
        for line in lsb_release_file:
            m = re.match(r'^CHROMEOS_RELEASE_BOARD=(.+)$', line)
            if m:
                return m.group(1)
    return None


# TODO(petermayo): crosbug.com/31826 Share this with _GsUpload in
# //chromite.git/buildbot/prebuilt.py somewhere/somehow
def gs_upload(local_file, remote_file, acl, result_dir=None,
              transfer_timeout=300, acl_timeout=300):
    """Upload to GS bucket.

    @param local_file: Local file to upload
    @param remote_file: Remote location to upload the local_file to.
    @param acl: name or file used for controlling access to the uploaded
                file.
    @param result_dir: Result directory if you want to add tracing to the
                       upload.
    @param transfer_timeout: Timeout for this upload call.
    @param acl_timeout: Timeout for the acl call needed to confirm that
                        the uploader has permissions to execute the upload.

    @raise CmdError: the exit code of the gsutil call was not 0.

    @returns True/False - depending on if the upload succeeded or failed.
    """
    # https://developers.google.com/storage/docs/accesscontrol#extension
    CANNED_ACLS = ['project-private', 'private', 'public-read',
                   'public-read-write', 'authenticated-read',
                   'bucket-owner-read', 'bucket-owner-full-control']
    _GSUTIL_BIN = 'gsutil'
    acl_cmd = None
    if acl in CANNED_ACLS:
        cmd = '%s cp -a %s %s %s' % (_GSUTIL_BIN, acl, local_file, remote_file)
    else:
        # For private uploads we assume that the overlay board is set up
        # properly and a googlestore_acl.xml is present, if not this script
        # errors
        cmd = '%s cp -a private %s %s' % (_GSUTIL_BIN, local_file, remote_file)
        if not os.path.exists(acl):
            logging.error('Unable to find ACL File %s.', acl)
            return False
        acl_cmd = '%s setacl %s %s' % (_GSUTIL_BIN, acl, remote_file)
    if not result_dir:
        base_utils.run(cmd, timeout=transfer_timeout, verbose=True)
        if acl_cmd:
            base_utils.run(acl_cmd, timeout=acl_timeout, verbose=True)
        return True
    with open(os.path.join(result_dir, 'tracing'), 'w') as ftrace:
        ftrace.write('Preamble\n')
        base_utils.run(cmd, timeout=transfer_timeout, verbose=True,
                       stdout_tee=ftrace, stderr_tee=ftrace)
        if acl_cmd:
            ftrace.write('\nACL setting\n')
            # Apply the passed in ACL xml file to the uploaded object.
            base_utils.run(acl_cmd, timeout=acl_timeout, verbose=True,
                           stdout_tee=ftrace, stderr_tee=ftrace)
        ftrace.write('Postamble\n')
        return True


def gs_ls(uri_pattern):
    """Returns a list of URIs that match a given pattern.

    @param uri_pattern: a GS URI pattern, may contain wildcards

    @return A list of URIs matching the given pattern.

    @raise CmdError: the gsutil command failed.

    """
    gs_cmd = ' '.join(['gsutil', 'ls', uri_pattern])
    result = base_utils.system_output(gs_cmd).splitlines()
    return [path.rstrip() for path in result if path]


def nuke_pids(pid_list, signal_queue=[signal.SIGTERM, signal.SIGKILL]):
    """
    Given a list of pid's, kill them via an esclating series of signals.

    @param pid_list: List of PID's to kill.
    @param signal_queue: Queue of signals to send the PID's to terminate them.
    """
    for sig in signal_queue:
        logging.debug('Sending signal %s to the following pids:', sig)
        for pid in pid_list:
            logging.debug('Pid %d', pid)
            try:
                os.kill(pid, sig)
            except OSError:
                # The process may have died from a previous signal before we
                # could kill it.
                pass
        time.sleep(CHECK_PID_IS_ALIVE_TIMEOUT)
    failed_list = []
    if signal.SIGKILL in signal_queue:
        return
    for pid in pid_list:
        if base_utils.pid_is_alive(pid):
            failed_list.append('Could not kill %d for process name: %s.' % pid,
                               base_utils.get_process_name(pid))
    if failed_list:
        raise error.AutoservRunError('Following errors occured: %s' %
                                     failed_list, None)


def externalize_host(host):
    """Returns an externally accessible host name.

    @param host: a host name or address (string)

    @return An externally visible host name or address

    """
    return socket.gethostname() if host in _LOCAL_HOST_LIST else host


def get_lab_status():
      """Grabs the current lab status and message.

      @returns a dict with keys 'lab_is_up' and 'message'. lab_is_up points
               to a boolean and message points to a string.
      """
      result = {'lab_is_up' : True, 'message' : ''}
      status_url = global_config.global_config.get_config_value('CROS',
              'lab_status_url')
      max_attempts = 5
      retry_waittime = 1
      for _ in range(max_attempts):
          try:
              response = urllib2.urlopen(status_url)
          except IOError as e:
              logging.debug('Error occured when grabbing the lab status: %s.',
                            e)
              time.sleep(retry_waittime)
              continue
          # Check for successful response code.
          if response.getcode() == 200:
              data = json.load(response)
              result['lab_is_up'] = data['general_state'] in LAB_GOOD_STATES
              result['message'] = data['message']
              return result
          time.sleep(retry_waittime)
      # We go ahead and say the lab is open if we can't get the status.
      logging.warn('Could not get a status from %s', status_url)
      return result


def check_lab_status(board=None):
    """Check if the lab is up and if we can schedule suites to run.

    Also checks if the lab is disabled for that particular board, and if so
    will raise an error to prevent new suites from being scheduled for that
    board.

    @param board: board name that we want to check the status of.

    @raises error.LabIsDownException if the lab is not up.
    @raises error.BoardIsDisabledException if the desired board is currently
                                           disabled.
    """
    # Ensure we are trying to schedule on the actual lab.
    if not (global_config.global_config.get_config_value('SERVER',
            'hostname').startswith('cautotest')):
        return

    # First check if the lab is up.
    lab_status = get_lab_status()
    if not lab_status['lab_is_up']:
        raise error.LabIsDownException('Chromium OS Lab is currently not up: '
                                       '%s.' % lab_status['message'])

    # Check if the board we wish to use is disabled.
    # Lab messages should be in the format of:
    # Lab is 'status' [boards not to be ran] (comment). Example:
    # Lab is Open [stumpy, kiev, x86-alex] (power_resume rtc causing duts to go
    # down)
    boards_are_disabled = re.search('\[(.*)\]', lab_status['message'])
    if board and boards_are_disabled:
        if board in boards_are_disabled.group(1):
            raise error.BoardIsDisabledException('Chromium OS Lab is '
                    'currently not allowing suites to be scheduled on board '
                    '%s: %s' % (board, lab_status['message']))
    return


def urlopen_socket_timeout(url, data=None, timeout=5):
    """
    Wrapper to urllib2.urlopen with a socket timeout.

    This method will convert all socket timeouts to
    TimeoutExceptions, so we can use it in conjunction
    with the rpc retry decorator and continue to handle
    other URLErrors as we see fit.

    @param url: The url to open.
    @param data: The data to send to the url (eg: the urlencoded dictionary
                 used with a POST call).
    @param timeout: The timeout for this urlopen call.

    @return: The response of the urlopen call.

    @raises: error.TimeoutException when a socket timeout occurs.
    """
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        return urllib2.urlopen(url, data=data)
    except urllib2.URLError as e:
        if type(e.reason) is socket.timeout:
            raise error.TimeoutException(str(e))
    finally:
        socket.setdefaulttimeout(old_timeout)


def get_sheriffs():
    """
    Polls the javascript file that holds the identity of the sheriff and
    parses it's output to return a list of chromium sheriff email addresses.
    The javascript file can contain the ldap of more than one sheriff, eg:
    document.write('sheriff_one, sheriff_two').

    @return: A list of chroium.org sheriff email addresses to cc on the bug
        if the suite that failed was the bvt suite. An empty list otherwise.
    """
    sheriff_ids = []
    for sheriff_js in _SHERIFF_JS.split(','):
        try:
            url_content = base_utils.urlopen('%s%s'% (
                _CHROMIUM_BUILD_URL, sheriff_js)).read()
        except (ValueError, IOError) as e:
            logging.error('could not parse sheriff from url %s%s: %s',
                           _CHROMIUM_BUILD_URL, sheriff_js, str(e))
        else:
            ldaps = re.search(r"document.write\('(.*)'\)", url_content)
            if not ldaps:
                logging.error('Could not retrieve sheriff ldaps for: %s',
                               url_content)
                continue
            sheriff_ids += ['%s@chromium.org'% alias.replace(' ', '')
                            for alias in ldaps.group(1).split(',')]
    return sheriff_ids
