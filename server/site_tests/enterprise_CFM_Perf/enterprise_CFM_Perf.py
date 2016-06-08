# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv, os, re, time

from autotest_lib.client.bin import utils, site_utils
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test, autotest, afe_utils

_MEASUREMENT_DURATION_SECONDS = 10
_TOTAL_TEST_DURATION_SECONDS = 30
_PERF_RESULT_FILE = 'perf.csv'


class enterprise_CFM_Perf(test.test):
    """This is a server test which clears device TPM and runs
    enterprise_RemoraRequisition client test to enroll the device in to hotrod
    mode. After enrollment is successful, it collects and logs cpu, memory and
    temperature data from the device under test."""
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
            for kv in MOSYS_OUTPUT_RE.finditer(self.client.run_output(cmd)):
                key, value = kv.groups()
                if key == 'reading':
                    value = int(value)
                values[key] = value
            return values['reading']


    def run_once(self, host=None):
        self.client = host

        tpm_utils.ClearTPMOwnerRequest(self.client)

        if self.client.servo:
            self.client.servo.switch_usbkey('dut')
            self.client.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
            self.client.servo.set('dut_hub1_rst1', 'off')

        autotest.Autotest(self.client).run_test('enterprise_RemoraRequisition',
                                                check_client_result=True)

        # TODO: Start a hangout session after device enrollment succeeds.
        start_time = time.time()
        perf_keyval = {}
        board_name = self.client.get_board().split(':')[1]
        build_id = afe_utils.get_build(self.client)
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

        # TODO: End the hangout session after performance data collection is
        # done.

        tpm_utils.ClearTPMOwnerRequest(self.client)
