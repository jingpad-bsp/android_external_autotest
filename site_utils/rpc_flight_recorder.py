#!/usr/bin/env python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Standalone service to monitor AFE servers and report to ts_mon"""
import sys
import time
import multiprocessing
import urllib2

import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.server import frontend
from chromite.lib import commandline
from chromite.lib import cros_logging as logging
from chromite.lib import metrics
from chromite.lib import ts_mon_config

METRIC_ROOT = 'chromeos/autotest/blackbox/afe_rpc'
METRIC_RPC_CALL_DURATIONS = METRIC_ROOT + '/rpc_call_durations'
METRIC_TICK = METRIC_ROOT + '/tick'
METRIC_MONITOR_ERROR = METRIC_ROOT + '/afe_monitor_error'

FAILURE_REASONS = {
        proxy.JSONRPCException: 'JSONRPCException',
        }


def afe_rpc_call(hostname):
    """Perform one rpc call set on server

    @param hostname: server's hostname to poll
    """
    afe_monitor = AfeMonitor(hostname)
    try:
        afe_monitor.run()
    except Exception as e:
        metrics.Counter(METRIC_MONITOR_ERROR).increment(
                fields={'target_hostname': hostname})
        logging.exception(e)


class RpcFlightRecorder(object):
    """Monitors a list of AFE"""
    def __init__(self, servers, poll_period=60):
        """
        @pram servers: list of afe services to monitor
        @pram poll_period: frequency to poll all services, in seconds
        """
        self._servers = set(servers)
        self._poll_period = poll_period
        self._pool = multiprocessing.Pool(processes=20)


    def poll_servers(self):
        """Blocking function that polls all servers and shards"""
        while(True):
            start_time = time.time()
            logging.debug('Starting Server Polling: %s' %
                          ', '.join(self._servers))

            self._pool.map(afe_rpc_call, self._servers)

            logging.debug('Finished Server Polling')

            metrics.Counter(METRIC_TICK).increment()

            wait_time = (start_time + self._poll_period) - time.time()
            if wait_time > 0:
                time.sleep(wait_time)

def _failed(fields, msg_str, reason, err=None):
    """Mark current run failed

    @param fields, ts_mon fields to mark as failed
    @param msg_str, message string to be filled
    @param reason: why it failed
    @param err: optional error to log more debug info
    """
    fields['success'] = False
    fields['failure_reason'] = reason
    logging.warning("%s failed - %s", msg_str, reason)
    if err:
        logging.debug("%s fail_err - %s", msg_str, str(err))

class AfeMonitor(object):
    """Object that runs rpc calls against the given afe frontend"""

    def __init__(self, hostname):
        """
        @param hostname: hostname of server to monitor, string
        """
        self._hostname = hostname
        self._afe = frontend.AFE(server=self._hostname)
        self._metric_fields = {'target_hostname': self._hostname}


    def run_cmd(self, cmd, expected=None):
        """Runs rpc command and log metrics

        @param cmd: string of rpc command to send
        @param expected: expected result of rpc
        """
        metric_fields = self._metric_fields.copy()
        metric_fields['command'] = cmd
        metric_fields['success'] = True
        metric_fields['failure_reason'] = ''

        with metrics.SecondsTimer(METRIC_RPC_CALL_DURATIONS,
                fields=dict(metric_fields)) as f:

            msg_str = "%s:%s" % (self._hostname, cmd)


            try:
                result = self._afe.run(cmd)
                logging.debug("%s result = %s", msg_str, result)
                if expected is not None and expected != result:
                    _failed(f, msg_str, 'IncorrectResponse')

            except urllib2.HTTPError as e:
                _failed(f, msg_str, 'HTTPError:%d' % e.code)

            except Exception as e:
                _failed(f, msg_str, FAILURE_REASONS.get(type(e), 'Unknown'),
                        err=e)

                if type(e) not in FAILURE_REASONS:
                    raise

            if f['success']:
                logging.info("%s success", msg_str)


    def run(self):
        """Tests server and returns the result"""
        self.run_cmd('get_server_time')
        self.run_cmd('ping_db', [True])


def get_parser():
    """Returns argparse parser"""
    parser = commandline.ArgumentParser(description=__doc__)

    parser.add_argument('-a', '--afe', action='append', default=[],
                        help='Autotest FrontEnd server to monitor')

    parser.add_argument('-p', '--poll-period', type=int, default=60,
                        help='Frequency to poll AFE servers')
    return parser


def main(argv):
    """Main function

    @param argv: commandline arguments passed
    """
    parser = get_parser()
    options = parser.parse_args(argv[1:])


    if not options.afe:
        options.afe = [global_config.global_config.get_config_value(
                        'SERVER', 'global_afe_hostname', default='cautotest')]

    with ts_mon_config.SetupTsMonGlobalState('rpc_flight_recorder',
                                             indirect=True):
        afe_monitor = RpcFlightRecorder(options.afe,
                                        poll_period=options.poll_period)
        afe_monitor.poll_servers()


if __name__ == '__main__':
    main(sys.argv)
