# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, signal

from autotest_lib.client.common_lib import error, utils

# Override default parser with our site parser.
# This is coordinated with site_monitor_db.py.
def check_parse(process_info):
    return process_info['comm'] == 'site_parse'


class SiteDroneUtility(object):


    def kill_processes(self, process_list):
        signal_queue = (signal.SIGCONT, signal.SIGTERM, signal.SIGKILL)
        try:
            logging.info('List of process to be killed: %s', process_list)
            utils.nuke_pids([process.pid for process in process_list],
                            signal_queue=signal_queue)
        except error.AutoservRunError as e:
            self._warn('Error occured when killing processes. Error: %s' % e)