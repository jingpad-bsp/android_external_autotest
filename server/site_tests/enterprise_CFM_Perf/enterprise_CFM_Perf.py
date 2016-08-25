# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import csv, datetime, os, re, time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory

_SHORT_TIMEOUT = 5
_MEASUREMENT_DURATION_SECONDS = 10
_TOTAL_TEST_DURATION_SECONDS = 600
_PERF_RESULT_FILE = 'perf.csv'


class enterprise_CFM_Perf(test.test):
    """This is a server test which clears device TPM and runs
    enterprise_RemoraRequisition client test to enroll the device in to hotrod
    mode. After enrollment is successful, it collects and logs cpu, memory and
    temperature data from the device under test."""
    version = 1


    def _cpu_usage(self):
        """Returns cpu usage in %."""
        cpu_usage_start = self.system_facade.get_cpu_usage()
        time.sleep(_MEASUREMENT_DURATION_SECONDS)
        cpu_usage_end = self.system_facade.get_cpu_usage()
        return self.system_facade.compute_active_cpu_time(cpu_usage_start,
                cpu_usage_end) * 100


    def _memory_usage(self):
        """Returns total used memory in %."""
        total_memory = self.system_facade.get_mem_total()
        return ((total_memory - self.system_facade.get_mem_free())
                * 100 / total_memory)


    def _temperature_data(self):
        """Returns temperature sensor data in fahrenheit."""
        ectool = self.client.run('which ectool', ignore_status=True)
        if not ectool.exit_status:
            ec_temp = self.system_facade.get_ec_temperatures()
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


    def enroll_device_and_start_hangout(self):
        """Enroll device into CFM and start hangout session."""
        current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        hangout_name = 'auto-hangout-' + current_time

        self.cfm_facade.enroll_device()
        self.cfm_facade.restart_chrome_for_cfm()
        self.cfm_facade.wait_for_telemetry_commands()

        if not self.cfm_facade.is_oobe_start_page():
            self.cfm_facade.wait_for_oobe_start_page()

        self.cfm_facade.skip_oobe_screen()
        self.cfm_facade.start_new_hangout_session(hangout_name)


    def collect_perf_data(self):
        """Use system facade to collect performance data from the DUT using
        xmlrpc and save it to csv file in results directory. Data collected
        includes:
                1. CPU usage
                2. Memory usage
                3. Thermal temperature
                4. Timestamp
                5. Board name
                6. Build id
        """
        start_time = time.time()
        perf_keyval = {}
        board_name = self.system_facade.get_current_board()
        build_id = self.system_facade.get_chromeos_release_version()
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


    def run_once(self, host=None):
        self.client = host

        factory = remote_facade_factory.RemoteFacadeFactory(
                host, no_chrome=True)
        self.system_facade = factory.create_system_facade()
        self.cfm_facade = factory.create_cfm_facade()

        tpm_utils.ClearTPMOwnerRequest(self.client)

        if self.client.servo:
            self.client.servo.switch_usbkey('dut')
            self.client.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
            time.sleep(_SHORT_TIMEOUT)
            self.client.servo.set('dut_hub1_rst1', 'off')
            time.sleep(_SHORT_TIMEOUT)

        try:
            self.enroll_device_and_start_hangout()
            self.collect_perf_data()
            self.cfm_facade.end_hangout_session()
        except Exception as e:
            raise error.TestFail(str(e))

        tpm_utils.ClearTPMOwnerRequest(self.client)
