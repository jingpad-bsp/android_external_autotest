# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import re

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils

LogcatLine = collections.namedtuple('LogcatLine', ['pid', 'tag', 'message'])

def wait_for_logcat_log(message_tag, message_pattern,
                        process_id=None, timeout_seconds=30, host=None):
    """Wait for a line to show up in logcat.

    @param message_tag: string "tag" of the line, as understood by logcat.
    @param message_pattern: regular expression pattern that describes the
            entire text of the message to look for (e.g. '.*' matches all
            messages).  This is in grep's regex language.
    @param process_id: optional integer process id to match on.
    @param timeout_seconds: number of seconds to wait for the log line.
    @param host: host object to look for the log line on.  Defaults to
            our local host.

    """
    run = host.run if host is not None else utils.run
    # This needs to match a line like:
    #   I( 1303) [0302/210332:INFO:main.cc(113)] logged message (update_engine)
    #
    # where:
    #   I( 1303) means that this was logged at the INFO level by process 1303.
    #   (update_engine) suffix means that the log tag was "update_engine".
    #   '[0302/210332:INFO:main.cc(113)] logged message' is the message text.
    process_id_pattern = '[0-9]+'
    if process_id is not None:
        process_id_pattern = str(process_id)
    grep_pattern = r'^.\( %s\) %s  \(%s\)$' % (
            process_id_pattern, message_pattern, message_tag)
    # This super exciting command works as follows:
    #  1) logcat streams logs to a subshell.
    #  2) The subshell greps through the logs for a particular line.
    #  3) After seeing the line, log and cause a SIGPIPE for logcat.
    result = run('logcat --format=process | '
                 '(grep -m 1 -E "%s"; log -tautotest "Found log %s")' % (
                         grep_pattern, message_pattern),
                 timeout=timeout_seconds,
                 ignore_timeout=True)
    if result is None:
        raise error.TestFail('Timed out waiting for a log with message "%s"' %
                             message_pattern)

    line = result.stdout.strip()
    match = re.match(r'^.\( (\d+)\) (.*) \(([^(]+)\)$', line)
    if match:
        return LogcatLine(pid=match.group(1),
                          message=match.group(2),
                          tag=match.group(3))
    raise error.TestError('Failed to match logcat line "%s"' % line)
