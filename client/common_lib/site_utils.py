# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import re
import signal
import socket
import sys
import time
import urllib2

from autotest_lib.client.common_lib import base_utils, error, global_config
from autotest_lib.client.cros import constants


# Keep checking if the pid is alive every second until the timeout (in seconds)
CHECK_PID_IS_ALIVE_TIMEOUT = 6

_LOCAL_HOST_LIST = ('localhost', '127.0.0.1')


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


def _lsbrelease_search(regex, group_id=0):
    """Searches /etc/lsb-release for a regex match.

    @param regex: Regex to match.
    @param group_id: The group in the regex we are searching for.
                     Default is group 0.

    @returns the string in the specified group if there is a match or None if
             not found.

    @raises IOError if /etc/lsb-release can not be accessed.
    """
    with open(constants.LSB_RELEASE) as lsb_release_file:
        for line in lsb_release_file:
            m = re.match(regex, line)
            if m:
                return m.group(group_id)
    return None


def get_current_board():
    """Return the current board name.

    @return current board name, e.g "lumpy", None on fail.
    """
    return _lsbrelease_search(r'^CHROMEOS_RELEASE_BOARD=(.+)$', group_id=1)


def get_chromeos_release_version():
    """
    @return chromeos version in device under test as string. None on fail.
    """
    return _lsbrelease_search(r'^CHROMEOS_RELEASE_VERSION=(.+)$', group_id=1)


def is_moblab():
    """Return if we are running on a Moblab system or not.

    @return the board string if this is a Moblab device or None if it is not.
    """
    try:
        return _lsbrelease_search(r'.*moblab')
    except IOError as e:
        logging.error('Unable to determine if this is a moblab system: %s', e)

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

    @return: A mapping of the signal name to the number of processes it
        was sent to.
    """
    sig_count = {}
    # Though this is slightly hacky it beats hardcoding names anyday.
    sig_names = dict((k, v) for v, k in signal.__dict__.iteritems()
                     if v.startswith('SIG'))
    for sig in signal_queue:
        logging.debug('Sending signal %s to the following pids:', sig)
        sig_count[sig_names.get(sig, 'unknown_signal')] = len(pid_list)
        for pid in pid_list:
            logging.debug('Pid %d', pid)
            try:
                os.kill(pid, sig)
            except OSError:
                # The process may have died from a previous signal before we
                # could kill it.
                pass
        pid_list = [pid for pid in pid_list if base_utils.pid_is_alive(pid)]
        if not pid_list:
            break
        time.sleep(CHECK_PID_IS_ALIVE_TIMEOUT)
    failed_list = []
    if signal.SIGKILL in signal_queue:
        return sig_count
    for pid in pid_list:
        if base_utils.pid_is_alive(pid):
            failed_list.append('Could not kill %d for process name: %s.' % pid,
                               base_utils.get_process_name(pid))
    if failed_list:
        raise error.AutoservRunError('Following errors occured: %s' %
                                     failed_list, None)
    return sig_count


def externalize_host(host):
    """Returns an externally accessible host name.

    @param host: a host name or address (string)

    @return An externally visible host name or address

    """
    return socket.gethostname() if host in _LOCAL_HOST_LIST else host


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
             urllib2.URLError for errors that not caused by timeout.
             urllib2.HTTPError for errors like 404 url not found.
    """
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        return urllib2.urlopen(url, data=data)
    except urllib2.URLError as e:
        if type(e.reason) is socket.timeout:
            raise error.TimeoutException(str(e))
        raise
    finally:
        socket.setdefaulttimeout(old_timeout)


def parse_chrome_version(version_string):
    """
    Parse a chrome version string and return version and milestone.

    Given a chrome version of the form "W.X.Y.Z", return "W.X.Y.Z" as
    the version and "W" as the milestone.

    @param version_string: Chrome version string.
    @return: a tuple (chrome_version, milestone). If the incoming version
             string is not of the form "W.X.Y.Z", chrome_version will
             be set to the incoming "version_string" argument and the
             milestone will be set to the empty string.
    """
    match = re.search('(\d+)\.\d+\.\d+\.\d+', version_string)
    ver = match.group(0) if match else version_string
    milestone = match.group(1) if match else ''
    return ver, milestone


def take_screenshot(dest_dir, fname_prefix, format='png'):
    """
    Take screenshot and save to a new file in the dest_dir.

    @param dest_dir: path, destination directory to save the screenshot.
    @param fname_prefix: string, prefix for output filename.
    @param format: string, file format ('png', 'jpg', etc) to use.

    @returns complete path to saved screenshot file.

    """
    if not _is_x_running():
        return

    next_index = len(glob.glob(
        os.path.join(dest_dir, '%s-*.%s' % (fname_prefix, format))))
    screenshot_file = os.path.join(
        dest_dir, '%s-%d.%s' % (fname_prefix, next_index, format))
    logging.info('Saving screenshot to %s.', screenshot_file)

    import_cmd = ('/usr/local/bin/import -window root -depth 8 %s' %
                  screenshot_file)

    _execute_screenshot_capture_command(import_cmd)

    return screenshot_file


def take_screen_shot_crop_by_height(fullpath, final_height, x_offset_pixels,
                                    y_offset_pixels):
    """
    Take a screenshot, crop to final height starting at given (x, y) coordinate.

    Image width will be adjusted to maintain original aspect ratio).

    @param fullpath: path, fullpath of the file that will become the image file.
    @param final_height: integer, height in pixels of resulting image.
    @param x_offset_pixels: integer, number of pixels from left margin
                            to begin cropping.
    @param y_offset_pixels: integer, number of pixels from top margin
                            to begin cropping.

    """

    params = {'height': final_height, 'x_offset': x_offset_pixels,
              'y_offset': y_offset_pixels, 'path': fullpath}

    import_cmd = ('/usr/local/bin/import -window root -depth 8 -crop '
                  'x%(height)d+%(x_offset)d+%(y_offset)d %(path)s' % params)

    _execute_screenshot_capture_command(import_cmd)

    return fullpath


def take_screenshot_crop(fullpath, box=None):
    """
    Take a screenshot using import tool, crop according to dim given by the box.

    @param fullpath: path, full path to save the image to.
    @param box: 4-tuple giving the upper left and lower right pixel coordinates.

    """

    if box:
        upperx, uppery, lowerx, lowery = box

        img_w = lowerx - upperx
        img_h = lowery - uppery

        import_cmd = ('/usr/local/bin/import -window root -depth 8 -crop '
                      '%dx%d+%d+%d' % (img_w, img_h, upperx, uppery))
    else:
        import_cmd = ('/usr/local/bin/import -window root -depth 8')

    _execute_screenshot_capture_command('%s %s' % (import_cmd, fullpath))


def get_dut_display_resolution():
    """
    Parses output of xrandr to determine the display resolution of the dut.

    @return: tuple, (w,h) resolution of device under test.
    """

    env_vars = 'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority'
    cmd = '%s xrandr | egrep -o "current [0-9]* x [0-9]*"' % env_vars
    output = base_utils.system_output(cmd)

    m = re.search('(\d+) x (\d+)', output)

    if len(m.groups()) == 2:
        return int(m.group(1)), int(m.group(2))
    else:
        return None


def _execute_screenshot_capture_command(import_cmd_string):
    """
    Executes command to capture a screenshot.

    Provides safe execution of command to capture screenshot by wrapping
    the command around a try-catch construct.

    @param import_cmd_string: string, screenshot capture command.

    """

    old_exc_type = sys.exc_info()[0]
    full_cmd = ('DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority %s' %
                import_cmd_string)
    try:
        base_utils.system(full_cmd)
    except Exception as err:
        # Do not raise an exception if the screenshot fails while processing
        # another exception.
        if old_exc_type is None:
            raise
        logging.error(err)


def _is_x_running():
    try:
        return int(base_utils.system_output('pgrep -o ^X$')) > 0
    except Exception:
        return False


def is_localhost(server):
    """Check if server is equivalent to localhost.

    @param server: Name of the server to check.

    @return: True if given server is equivalent to localhost.
    @raise socket.gaierror: If server name failed to be resolved.
    """
    if server in _LOCAL_HOST_LIST:
        return True
    try:
        return (socket.gethostbyname(socket.gethostname()) ==
                socket.gethostbyname(server))
    except socket.gaierror:
        logging.error('Failed to resolve server name %s.', server)
        return False
