# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv, os, re, time

from autotest_lib.client.bin import site_utils, test, utils

_MEASUREMENT_DURATION_SECONDS = 10
_TOTAL_TEST_DURATION_SECONDS = 60
_PERF_RESULT_FILE = 'perf.csv'


class enterprise_CFM_Perf(test.test):
    """Captures cpu, memory and temperature data at set interval and stores it
    in resultsdir of test logs to be uploaded to Google Cloud Storage."""
    version = 1


    def _cpu_usage(self):
        """Returns cpu usage in %."""
        cpu_usage_start = site_utils.get_cpu_usage()
        time.sleep(_MEASUREMENT_DURATION_SECONDS)
        cpu_usage_end = site_utils.get_cpu_usage()
        return site_utils.compute_active_cpu_time(cpu_usage_start,
                                                  cpu_usage_end) * 100


    def _memory_usage(self):
        """Returns total used memory in %."""
        total_memory = site_utils.get_mem_total()
        return (total_memory - site_utils.get_mem_free()) * 100 / total_memory


    def _temperature_data(self):
        """Returns temperature sensor data in fahrenheit."""
        if (utils.system('which ectool', ignore_status=True) == 0):
            ec_temp = site_utils.get_ec_temperatures()
            return ec_temp[1]
        else:
            temp_sensor_name = 'temp0'
            if not temp_sensor_name:
                return 0
            MOSYS_OUTPUT_RE = re.compile('(\w+)="(.*?)"')
            values = {}
            cmd = 'mosys -k sensor print thermal %s' % temp_sensor_name
            for kv in MOSYS_OUTPUT_RE.finditer(utils.system_output(cmd)):
                key, value = kv.groups()
                if key == 'reading':
                    value = int(value)
                values[key] = value
            return values['reading']


    def run_once(self):
        start_time = time.time()
        perf_keyval = {}
        board_name = utils.get_current_board()
        build_id = utils.get_chromeos_release_version()
        perf_file = open(os.path.join(self.resultsdir, _PERF_RESULT_FILE), 'w')
        writer = csv.writer(perf_file)
        writer.writerow(['cpu', 'memory', 'temperature', 'timestamp', 'board',
                         'build'])
        while (time.time() - start_time) < _TOTAL_TEST_DURATION_SECONDS:
            perf_keyval['cpu_usage'] = self._cpu_usage()
            perf_keyval['memory_usage'] = self._memory_usage()
            perf_keyval['temperature'] = self._temperature_data()
            writer.writerow([perf_keyval['cpu_usage'],
                             perf_keyval['memory_usage'],
                             perf_keyval['temperature'],
                             time.strftime('%Y/%m/%d %H:%M:%S'),
                             board_name,
                             build_id])
            self.write_perf_keyval(perf_keyval)
            time.sleep(_MEASUREMENT_DURATION_SECONDS)
        perf_file.close()
        utils.write_keyval(os.path.join(self.resultsdir, os.pardir),
                           {'perf_csv_folder': self.resultsdir})
