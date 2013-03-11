# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
import socket

import common

from autotest_lib.client.common_lib import global_config


# Pylint locally complains about "No value passed for parameter 'key'" here
# pylint: disable=E1120
CARBON_SERVER = global_config.global_config.get_config_value('CROS',
        'CARBON_SERVER')
CARBON_PORT = global_config.global_config.get_config_value('CROS',
        'CARBON_PORT', int)


def send_data(lines, add_time=True, debug=False, process_queue=20):
    """Send data to the statsd/graphite server.

    Example of a line "autotest.scheduler.running_agents_5m 300"
    5m is the frequency we are sampling (It is not required but it adds clarity
    to the metric).
    @param lines: A list of lines of the format "category value"
    @param add_time: Optional, if you do not want send_data to automatically
        add a timestamp set this to False. However your lines of data will need
        to be of the format "category value timestamp" [default: True]
    @param debug: Print out what you would send but do not send anything.
        [default: False]
    @param process_queue: How many lines to send to the statsd server at a
        time. [defualt: 20]
    @returns True on success, False on failure.
    """
    sock = socket.socket()
    if add_time:
        now = int(time.time())
        for index in xrange(0, len(lines)):
            lines[index] += ' %d' % now

    try:
      sock.connect( (CARBON_SERVER, CARBON_PORT) )
    except EnvironmentError:
        return False

    slices = [lines[i:i+process_queue] for i in range(0, len(lines),
                                                      process_queue)]
    for lines in slices:
        data = '\n'.join(lines) + '\n'
        if debug:
            print 'Slice:\n%s' % data
            continue
        sock.sendall(data)

    return True
