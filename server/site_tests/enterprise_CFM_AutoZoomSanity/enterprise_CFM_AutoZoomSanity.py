# Copyright (c) 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, os, time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import perf_stat_lib
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test
from autotest_lib.server.cros import cfm_jmidata_log_collector
from autotest_lib.server.cros.multimedia import remote_facade_factory


_BASE_DIR = '/home/chronos/user/Storage/ext/'
_EXT_ID = 'ikfcpmgefdpheiiomgmhlmmkihchmdlj'
_JMI_DIR = '/0*/File\ System/000/t/00/*'
_JMI_SOURCE_DIR = _BASE_DIR + _EXT_ID + _JMI_DIR
_USB_DIR = '/sys/bus/usb/devices'
LONG_TIMEOUT = 10
SHORT_TIMEOUT = 5


class enterprise_CFM_AutoZoomSanity(test.test):
    """Auto Zoom Sanity test."""
    version = 1

    def get_data_from_jmifile(self, data_type, jmidata):
        """ Gets data from jmidata log for given data type.

        @param data_type: Type of data to be retrieved from jmi data log.
        @param jmidata: Raw jmi data log to parse.
        @returns Data for given data type from jmidata log.
        """
        return cfm_jmidata_log_collector.GetDataFromLogs(
                self, data_type, jmidata)


    def get_file_to_parse(self):
        """ Copy jmi logs from client to test's results directory.

        @returns The newest jmi log file.
        """
        self.client.get_file(_JMI_SOURCE_DIR, self.resultsdir)
        source_jmi_files = self.resultsdir + '/0*'
        if not source_jmi_files:
            raise error.TestNAError('JMI data file not found.')
        newest_file = max(glob.iglob(source_jmi_files), key=os.path.getctime)
        return newest_file


    def verify_cfm_sent_resolution(self):
        """ Check / verify CFM sent video resolution data from JMI logs."""
        jmi_file = self.get_file_to_parse()
        jmifile_to_parse = open(jmi_file, 'r')
        jmidata = jmifile_to_parse.read()

        cfm_sent_res_list = self.get_data_from_jmifile(
                'video_sent_frame_height', jmidata)
        percentile_95 = perf_stat_lib.get_kth_percentile(
                cfm_sent_res_list, 95)

        self.output_perf_value(description='video_sent_frame_height',
                               value=cfm_sent_res_list,
                               units='resolution',
                               higher_is_better=True)
        self.output_perf_value(description='95th percentile res sent',
                               value=percentile_95,
                               units='resolution',
                               higher_is_better=True)

        # TODO(dkaeding): Add logic to examine the cfm sent resolution and
        # take appropriate action.
        logging.info('95th percentile of outgoing video resolution: %s',
                     percentile_95)


    def check_verify_rtanalytics_logs(self):
        """ Verify needed information in rtanalytics logs."""
        # TODO(dkaeding): Implement this method.
        return NotImplemented


    def get_usb_device_dirs(self):
        """ Gets usb device dirs from _USB_DIR path.

        @returns list with number of device dirs else None
        """
        usb_dir_list = list()
        cmd = 'ls %s' % _USB_DIR
        cmd_output = self.client.run(cmd).stdout.strip().split('\n')
        for d in cmd_output:
            usb_dir_list.append(os.path.join(_USB_DIR, d))
        return usb_dir_list


    def file_exists_on_host(self, path):
        """ Checks if file exists on host.

        @param path: File path
        @returns True or False
        """
        return self.client.run('ls %s' % path,
                               ignore_status=True).exit_status == 0


    def check_peripherals(self, peripheral_dict):
        """ Check and verify correct peripherals are attached.

        @param peripheral_dict: dict of peripherals that should be connected
        """
        usb_dir_list = self.get_usb_device_dirs()
        peripherals_found = list()
        for d_path in usb_dir_list:
            file_name = os.path.join(d_path, 'product')
            if self.file_exists_on_host(file_name):
                peripherals_found.append(self.client.run(
                        'cat %s' % file_name).stdout.strip())

        logging.info('Attached peripherals: %s', peripherals_found)

        for peripheral in peripheral_dict:
            if peripheral not in peripherals_found:
                raise error.TestFail('%s not found.' % peripheral)


    def run_once(self, host, session_length, peripheral_dict):
        self.client = host

        factory = remote_facade_factory.RemoteFacadeFactory(
                host, no_chrome=True)
        self.cfm_facade = factory.create_cfm_facade()

        tpm_utils.ClearTPMOwnerRequest(self.client)

        # Enable USB port on the servo so device can see and talk to the
        # attached peripheral.
        if self.client.servo:
            self.client.servo.switch_usbkey('dut')
            self.client.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
            time.sleep(SHORT_TIMEOUT)
            self.client.servo.set('dut_hub1_rst1', 'off')
            time.sleep(SHORT_TIMEOUT)

        try:
            self.check_peripherals(peripheral_dict)
            self.cfm_facade.enroll_device()

            # The following reboot and sleep are a hack around devtools crash
            # issue tracked in crbug.com/739474.
            self.client.reboot()
            time.sleep(SHORT_TIMEOUT)
            self.cfm_facade.skip_oobe_after_enrollment()
            self.cfm_facade.wait_for_meetings_telemetry_commands()
            self.cfm_facade.start_meeting_session()
            time.sleep(session_length)
            self.cfm_facade.end_meeting_session()
            self.verify_cfm_sent_resolution()
            self.check_verify_rtanalytics_logs()
        except Exception as e:
            raise error.TestFail(str(e))
        finally:
            tpm_utils.ClearTPMOwnerRequest(self.client)
