# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import re
import socket

from autotest_lib.client.common_lib import base_utils, global_config

def ping(host, deadline=None, tries=None, timeout=60):
    """Attempt to ping |host|.

    Shell out to 'ping' to try to reach |host| for |timeout| seconds.
    Returns exit code of ping.

    Per 'man ping', if you specify BOTH |deadline| and |tries|, ping only
    returns 0 if we get responses to |tries| pings within |deadline| seconds.

    Specifying |deadline| or |count| alone should return 0 as long as
    some packets receive responses.

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
