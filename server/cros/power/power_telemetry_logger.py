# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper class for power measurement with telemetry devices."""

import collections
import datetime
from distutils import sysconfig
import json
import logging
import numpy
import os
import re
import shutil
import string
import time
import threading

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.power import power_telemetry_utils
from autotest_lib.server.cros.power import power_dashboard

DASHBOARD_UPLOAD_URL = 'http://chrome-power.appspot.com'
DEFAULT_START = r'starting test\(run_once\(\)\), test details follow'
DEFAULT_END = r'The test has completed successfully'
DEFAULT_SWEETBERRY_INTERVAL = 20.0
# TODO(mqg): have Sweetberry try the file name with prescribed set of paths.
SWEETBERRY_CONFIG_DIR = os.path.join(
        sysconfig.get_python_lib(standard_lib=False), 'servo', 'data')

def ts_processing(ts_str):
    """Parse autotest log timestamp into local seconds since epoch.

    @param ts_str: a timestamp string from client.DEBUG file.
    @returns seconds since epoch in local time, inserting the current year
             because ts_str does not include year. This introduces error if
             PowerTelemetryLogger is running across the turn of the year.
    """
    ts = datetime.datetime.strptime(ts_str, '%m/%d %H:%M:%S.%f ')
    # TODO(mqg): fix the wrong year at turn of the year.
    ts = ts.replace(year=datetime.datetime.today().year)
    return time.mktime(ts.timetuple()) + ts.microsecond / 1e6

def get_sweetberry_config_path(filename):
    """Get the absolute path for Sweetberry board and scenario file.

    @param filename: string of Sweetberry config filename.
    @returns a tuple of the path to Sweetberry board file and the path to
             Sweetberry scenario file.
    @raises error.TestError if board file or scenario file does not exist in
            file system.
    """
    board_path = os.path.join(SWEETBERRY_CONFIG_DIR, '%s.board' % filename)
    if not os.path.isfile(board_path):
        msg = 'Sweetberry board file %s does not exist.' % board_path
        raise error.TestError(msg)

    scenario_path = os.path.join(SWEETBERRY_CONFIG_DIR,
                                 '%s.scenario' % filename)
    if not os.path.isfile(scenario_path):
        msg = 'Sweetberry scenario file %s does not exist.' % scenario_path
        raise error.TestError(msg)
    return (board_path, scenario_path)

class SweetberryThread(threading.Thread):
    """A thread that starts and ends Sweetberry measurement."""

    def __init__(self, board, scenario, interval, stats_json_dir, end_flag,
                 serial=None):
        """
        Initialize the Sweetberry thread.

        Once started, this thread will invoke Sweetberry powerlog tool every
        [interval] seconds, which will sample each rail in [scenario] file
        multiple times and write the average of those samples in json format to
        [stats_json_dir]. The resistor size of each power rail is specified in
        [board] file.

        See go/sweetberry and go/sweetberry-readme for more details.

        @param board: file name for Sweetberry board file.
        @param scenario: file name for Sweetberry scenario file.
        @param interval: time of each Sweetberry run cycle; print Sweetberry
                         data every <interval> seconds.
        @param stats_json_dir: directory to store Sweetberry stats in json.
        @param end_flag: event object, stop Sweetberry measurement when this is
                         set.
        @param serial: serial number of sweetberry
        """
        threading.Thread.__init__(self, name='Sweetberry')
        self._end_flag = end_flag
        self._interval = interval
        self._argv = ['--board', board,
                      '--config', scenario,
                      '--save_stats_json', stats_json_dir,
                      '--no_print_raw_data',
                      '--mW']
        if serial:
            self._argv.extend(['--serial', serial])

    def run(self):
        """Start Sweetberry measurement until end_flag is set."""
        logging.debug('Sweetberry starts.')
        loop = 0
        start_timestamp = time.time()
        while not self._end_flag.is_set():
            # TODO(mqg): in the future use more of powerlog components
            # explicitly, make a long call and harvest data from Sweetberry,
            # instead of using it like a command line tool now.
            loop += 1
            next_loop_start_timestamp = start_timestamp + loop * self._interval
            current_timestamp = time.time()
            this_loop_duration = next_loop_start_timestamp - current_timestamp
            args = ['powerlog']
            args.extend(self._argv)
            args.extend(['--seconds', str(this_loop_duration)])
            os.system(' '.join(args))
        logging.debug('Sweetberry stops.')


class PowerTelemetryLogger(object):
    """An helper class for power autotests requiring telemetry devices.

    Telemetry: external pieces of hardware which help with measuring power
    statistics on the Chromebook. This is not to be confused with library
    telemetry.core, which is a required library / dependency for autotests
    involving Chrome and / or ARC. Examples of power telemetry devices include
    servo and Sweetberry.

    This logger class detects telemetry devices connected to the DUT. It will
    then start and stop the measurement, trim the excessive power telemetry
    device logs and report the data back to the workstation and the dashboard.

    """

    def __init__(self, config, resultsdir, host):
        """
        Init PowerTelemetryLogger.

        @param config: dict of parsed arguments from test_that. Settings for
                       power telemetry devices.
        @param resultsdir: path to directory where autotests results are stored.
                           e.g.
                           /tmp/test_that_results/results-1-test_TestName.tag
        @param host: the device under test (Chromebook).
        """
        logging.debug('%s initialize.', self.__class__.__name__)
        self._interval = DEFAULT_SWEETBERRY_INTERVAL
        if 'sweetberry_interval' in config:
            self._interval = float(config['sweetberry_interval'])
        self._sweetberry_serial = config.get('sweetberry_serial', None)
        self._note = config.get('note', '')
        self._logdir = os.path.join(resultsdir, 'power_telemetry_log')
        self._end_flag = threading.Event()
        self._host = host
        if 'sweetberry_config' in config:
            self._sweetberry_config = config['sweetberry_config']
        else:
            board = self._host.get_board().replace('board:', '')
            hardware_rev = self._host.get_hardware_revision()
            self._sweetberry_config = board + '_' + hardware_rev
        board_path, scenario_path = \
                get_sweetberry_config_path(self._sweetberry_config)
        self._tagged_testname = config['test']
        self._sweetberry_thread = SweetberryThread(
                board=board_path,
                scenario=scenario_path,
                interval=self._interval,
                stats_json_dir=self._logdir,
                end_flag=self._end_flag,
                serial=self._sweetberry_serial)
        self._sweetberry_thread.setDaemon(True)

    def start_measurement(self):
        """Start power telemetry devices."""
        logging.info('%s starts.', self.__class__.__name__)
        self._sweetberry_thread.start()

    def end_measurement(self, debug_file_path):
        """
        End power telemetry devices.

        End power measurement with telemetry devices, parse the power telemetry
        devices logs, trim the logs with timestamp outside of run_once() in
        autotest, and upload statistics to dashboard.

        @param debug_file_path: Path to the file which contains autotest debug
                                logs.
        """
        self._end_flag.set()
        # Sweetberry thread should theoretically finish within 1 self._interval
        # but giving 2 here to be more lenient.
        self._sweetberry_thread.join(self._interval * 2)
        if self._sweetberry_thread.is_alive():
            logging.warning('%s %s thread did not finish. There might be extra '
                            'data at the end.', self.__class__.__name__,
                            self._sweetberry_thread.name)
        else:
            logging.info('%s finishes.', self.__class__.__name__)

        self._trim_log(debug_file_path)

        self._upload_data()

    def _trim_log(self, debug_file_path):
        """
        Trim the telemetry logs.

        Power telemetry devices will run through the entire autotest, but we
        only need the measurements within run_once(), so delete all unnecessary
        logs.

        @param debug_file_path: File path of the autotest debug log.
        """
        if not os.path.exists(self._logdir):
            logging.error('Cannot find %s, no Sweetberry measurements exist.',
                          self._logdir)
            return

        if not os.path.isfile(debug_file_path):
            logging.error('Cannot find test debug log %s, no need to trim '
                          'Sweetberry measurements.', debug_file_path)
            return

        default_test_events = collections.defaultdict(dict)
        custom_test_events = collections.defaultdict(dict)
        default_test_events['start']['str'] = DEFAULT_START
        default_test_events['end']['str'] = DEFAULT_END
        custom_test_events['start']['str'] = power_telemetry_utils.CUSTOM_START
        custom_test_events['end']['str'] = power_telemetry_utils.CUSTOM_END
        for event in default_test_events:
            default_test_events[event]['re'] = \
                    re.compile(r'([\d\/\.\:\s]+).+' +
                               default_test_events[event]['str'])
        for event in custom_test_events:
            custom_test_events[event]['re'] = \
                    re.compile(r'.*' + custom_test_events[event]['str'] +
                               r'\s+([\d\.]+)')

        debug_log = open(debug_file_path, 'r')

        for line in debug_log:
            for event in default_test_events:
                match = default_test_events[event]['re'].match(line)
                if match:
                    default_test_events[event]['ts'] = \
                            ts_processing(match.group(1))
            for event in custom_test_events:
                match = custom_test_events[event]['re'].match(line)
                if match:
                    custom_test_events[event]['ts'] = float(match.group(1))

        events_ts = {
            'start': 0,
            'end': time.time(),
        }
        for event in events_ts:
            events_ts[event] = default_test_events[event].get(
                    'ts', events_ts[event])
            events_ts[event] = custom_test_events[event].get(
                    'ts', events_ts[event])
            events_ts[event] += self._interval / 2.0

        for sweetberry_file in os.listdir(self._logdir):
            if sweetberry_file.startswith('sweetberry'):
                sweetberry_ts = float(string.lstrip(
                        sweetberry_file, 'sweetberry'))
                if (sweetberry_ts < events_ts['start'] or
                        sweetberry_ts > events_ts['end']):
                    shutil.rmtree(os.path.join(self._logdir, sweetberry_file))

        debug_log.close()

    def _upload_data(self):
        """
        Combine results from Sweetberry data directory and format it to be
        ready for dashboard. Then upload the data to dashboard.

        Data format:
        {
            "sample_count" : 60,
            "sample_duration" : 60,
            "data" : {
                "domain_1" : [ 111.11, 123.45 , ... , 99.99 ],
                ...
                "domain_n" : [ 3999.99, 4242.42, ... , 4567.89 ]
            },
            "average" : {
                "domain_1" : 100.00,
                ...
                "domain_n" : 4300.00
            }
            "unit" : {
                "domain_1" : "milliwatt",
                ...
                "domain_n" : "milliwatt"
            }
        }
        """
        if not os.path.exists(self._logdir):
            logging.error('Cannot find %s, no Sweetberry measurements exist, '
                          'not uploading to dashboard.', self._logdir)
            return

        data = collections.defaultdict(lambda: [])
        for sweetberry_file in sorted(os.listdir(self._logdir)):
            if sweetberry_file.startswith('sweetberry'):
                fname = os.path.join(self._logdir, sweetberry_file,
                                     'summary.json')
                with open(fname, 'r') as f:
                    d = json.load(f)
                    for k, v in d.iteritems():
                        data[k].append(v['mean'])

        logger = {
            # All data domains should have same sample count.
            'sample_count': len(data.itervalues().next()),
            'sample_duration': self._interval,
            'data': data,
            'average': {k: numpy.average(v) for k, v in data.iteritems()},
            # TODO(mqg): hard code the units for now because we are only dealing
            # with power so far. When we start to work with voltage or current,
            # read the units from the .json files.
            'unit': {k: 'milliwatt' for k in data},
            'type': {k: 'sweetberry' for k in data},
        }

        pdash = power_dashboard.PowerTelemetryLoggerDashboard(
                logger=logger, testname=self._tagged_testname, host=self._host,
                resultsdir=self._logdir, uploadurl=DASHBOARD_UPLOAD_URL,
                note=self._note)
        pdash.upload()
