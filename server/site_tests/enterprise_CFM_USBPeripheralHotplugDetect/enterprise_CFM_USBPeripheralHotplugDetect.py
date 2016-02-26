# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time, re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test, autotest

_WAIT_DELAY = 15
_USB_DIR = '/sys/bus/usb/devices'
_JMI_LOGS_FILE = '/tmp/jmilogs.log'


class enterprise_CFM_USBPeripheralHotplugDetect(test.test):
    """Uses servo to hotplug and detect USB peripherals on CrOS and hotrod. It
    compares attached audio/video peripheral names on CrOS against what hotrod
    sees based on the JIM data logs that are saved in the /tmp dir on DUT."""
    version = 1


    def _set_hub_power(self, on=True):
        """Setting USB hub power status

        @param on: To power on the servo usb hub or not.

        """
        reset = 'off'
        if not on:
            reset = 'on'
        self.host.servo.set('dut_hub1_rst1', reset)
        time.sleep(_WAIT_DELAY)


    def _get_usb_device_dirs(self):
        """Gets usb device dirs from _USB_DIR path.

        @returns list with number of device dirs else Non

        """
        usb_dir_list = list()
        cmd = 'ls %s' % _USB_DIR
        cmd_output = self.host.run(cmd).stdout.strip().split('\n')
        for d in cmd_output:
            usb_dir_list.append(os.path.join(_USB_DIR, d))
        return usb_dir_list


    def _get_usb_device_type(self, vendor_id):
        """Gets usb device type info from lsusb output based on vendor id.

        @vendor_id: Device vendor id.
        @returns list of device types associated with vendor id

        """
        details_list = list()
        cmd = 'lsusb -v -d ' + vendor_id + ': | head -150'
        cmd_out = self.host.run(cmd).stdout.strip().split('\n')
        for line in cmd_out:
            if (any(phrase in line for phrase in ('bInterfaceClass',
                    'wTerminalType'))):
                details_list.append(line.split(None)[2])

        return list(set(details_list))


    def _get_product_info(self, directory, prod_string):
        """Gets the product name from device path.

        @param directory: Driver path for USB device.
        @param prod_string: Device attribute string.
        @returns the output of the cat command

        """
        product_file_name = os.path.join(directory, prod_string)
        if self._file_exists_on_host(product_file_name):
            return self.host.run('cat %s' % product_file_name).stdout.strip()
        return None


    def _parse_device_dir_for_info(self, dir_list):
        """Uses device path and vendor id to get device type attibutes.

        @param dir_list: Complete list of device directories.
        @returns cros_peripheral_dict with device names

        """
        list_of_usb_device_dictionaries = list()
        cros_peripheral_dict = {'Camera': None, 'Microphone': None,
                                'Speaker': None}

        for d_path in dir_list:
            file_name = os.path.join(d_path, 'idVendor')
            if self._file_exists_on_host(file_name):
                vendor_id = self.host.run('cat %s' % file_name).stdout.strip()
                device_types = self._get_usb_device_type(vendor_id)
                if 'Microphone' in device_types:
                    cros_peripheral_dict['Microphone'] = (
                            self._get_product_info(d_path, 'product'))
                if 'Speaker' in device_types:
                    cros_peripheral_dict['Speaker'] = (
                            self._get_product_info(d_path, 'product'))
                if 'Video' in device_types:
                    cros_peripheral_dict['Camera'] = (
                            self._get_product_info(d_path, 'product'))

        for device_type, is_found in cros_peripheral_dict.iteritems():
            if not is_found:
                cros_peripheral_dict[device_type] = 'Not Found'

        return cros_peripheral_dict


    def _parse_peripheral_jmidata(self, jmidata):
        """Parses jmidata log file to extract peripheral names.

        @param jmidata: Jmi log file to be parsed.
        @returns jmi_peripheral_dict with device names

        """
        list_of_peripheral_dict = list()
        jmi_peripheral_dict = {'Camera': None, 'Microphone': None,
                           'Speaker': None}

        PERIPHERAL_RE = '\/''.*?''(?=\/)'
        for line in jmidata.splitlines():
            if 'talk.media.webrtc.DeviceChannel' in line:
                logging.debug('Jmi peripheral data: %s', line)
                if ('Microphone' in line and
                        jmi_peripheral_dict['Microphone'] is None):
                    jmi_peripheral_dict['Microphone'] = (re.search(
                            PERIPHERAL_RE, line).group().strip('/'))
                if 'Speaker' in line and jmi_peripheral_dict['Speaker'] is None:
                    jmi_peripheral_dict['Speaker'] = (re.search(
                            PERIPHERAL_RE, line).group().strip('/'))
                if 'Camera' in line and jmi_peripheral_dict['Camera'] is None:
                    jmi_peripheral_dict['Camera'] = (re.search(
                            PERIPHERAL_RE, line).group().strip('/'))

        for device_type, is_found in jmi_peripheral_dict.iteritems():
            if not is_found:
                jmi_peripheral_dict[device_type] = 'Not Found'

        return jmi_peripheral_dict


    def _file_exists_on_host(self, path):
        """Checks if file exists on host.

        @param path: File path
        @returns True or False

        """
        return self.host.run('ls %s' % path,
                             ignore_status=True).exit_status == 0


    def _read_jmidata(self, filename):
        """Copies jmi logs to autotest resultsdir and returns its content.

        @param filename: Name of the file to copy jmi logs to
        @returns File contents

        """
        if not self._file_exists_on_host(_JMI_LOGS_FILE):
            raise error.TestError('Jmi log file does not exist.')

        f = open(filename, 'w')
        self.host.run('cat %s' % _JMI_LOGS_FILE, stdout_tee=f)
        f.close()

        return utils.read_file(filename)


    def run_once(self, host):
        """Main function to run autotest.

        @param host: Host object representing the DUT.

        """
        self.host = host

        tpm_utils.ClearTPMOwnerRequest(self.host)
        autotest.Autotest(self.host).run_test('enterprise_RemoraRequisition')

        self.host.servo.switch_usbkey('dut')
        self.host.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
        time.sleep(_WAIT_DELAY)

        self._set_hub_power(False)
        usb_list_dir_off = self._get_usb_device_dirs()

        self._set_hub_power(True)
        usb_list_dir_on = self._get_usb_device_dirs()

        diff_list = list(set(usb_list_dir_on).difference(set(usb_list_dir_off)))

        if len(diff_list) == 0:
            raise error.TestError('No connected devices were detected. Make '
                                  'sure the devices are connected to USB_KEY '
                                  'and DUT_HUB1_USB on the servo board.')

        cros_peripheral_dict = self._parse_device_dir_for_info(diff_list)
        logging.debug('Peripherals detected by CrOS: %s', cros_peripheral_dict)

        jmidata_logs_filename = os.path.join(self.resultsdir, 'jmidata')
        jmidata = self._read_jmidata(jmidata_logs_filename)
        jmi_peripheral_dict = self._parse_peripheral_jmidata(jmidata)
        logging.debug('Peripherals detected by hotrod: %s', jmi_peripheral_dict)

        cros_peripherals = set(cros_peripheral_dict.iteritems())
        jmi_peripherals = set(jmi_peripheral_dict.iteritems())

        peripheral_diff = cros_peripherals.difference(jmi_peripherals)

        tpm_utils.ClearTPMOwnerRequest(self.host)

        if peripheral_diff:
            no_match_list = list()
            for item in peripheral_diff:
                no_match_list.append(item[0])

            raise error.TestFail('Following peripherals do not match: %s' %
                                ', '.join(no_match_list))

