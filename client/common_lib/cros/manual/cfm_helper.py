# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Check USB device by running cli on CfM"""

from __future__ import print_function

import logging
import re
import time
from autotest_lib.client.common_lib.cros.manual import get_usb_devices
from autotest_lib.client.common_lib.cros import power_cycle_usb_util

CORE_DIR_LINES = 3
ATRUS = '18d1:8001'

def check_is_platform(dut, name, debug):
    """
    Check whether CfM is expected platform.
    @param dut: The handle of the device under test.
    @param name: The name of platform
    @param debug: if True output of cli and output are sent to stdout,
                  else, not
    @returns: True, if CfM's platform is same as expected.
              False, if not.
    """
    cmd = ("cat /var/log/platform_info.txt | grep name | "
           "awk -v N=3 \'{print $N}\'")
    output = dut.run(cmd, ignore_status=True).stdout.split()[0]
    if debug:
        logging.info('---cmd: %s', cmd)
        logging.info('---output: %s', output.lower())
    return output.lower() == name


def get_mgmt_ipv4(dut):
    """
    Get mgmt ipv4 address
    @param dut: The handle of the device under test. Should be initialized in
                 autotest.
    @return: ipv4 address for mgmt interface.
    """
    cmd = 'ifconfig -a | grep eth0 -A 2 | grep netmask'
    try:
        output = dut.run(cmd, ignore_status=True).stdout
    except Exception as e:
        logging.info('Fail to run cli %s, reason: %s', cmd, str(e))
        return None
    ipv4 = re.findall(r"inet\s*([0-9.]+)\s*netmask.*", output)[0]
    return ipv4


def retrieve_usb_devices(dut):
    """
    Populate output of usb-devices on CfM.
    @param dut: handle of CfM under test
    @returns dict of all usb devices detected on CfM.
    """
    usb_devices = (dut.run('usb-devices', ignore_status=True).
                   stdout.strip().split('\n\n'))
    usb_data = get_usb_devices.extract_usb_data(
               '\nUSB-Device\n'+'\nUSB-Device\n'.join(usb_devices))
    return usb_data


def extract_peripherals_for_cfm(usb_data, debug):
    """
    Check CfM has camera, speaker and Mimo connected.
    @param usb_data: dict extracted from output of "usb-devices"
    @param debug: if True, print out extracted usb devices to stdout.
                  else, not print out.
    """
    peripheral_map = {}

    speaker_list = get_usb_devices.get_speakers(usb_data)
    camera_list = get_usb_devices.get_cameras(usb_data)
    display_list = get_usb_devices.get_display_mimo(usb_data)
    controller_list = get_usb_devices.get_controller_mimo(usb_data)

    for _key in speaker_list.keys():
        if speaker_list[_key] != 0:
            peripheral_map[_key] = speaker_list[_key]

    for _key in camera_list.keys():
        if camera_list[_key] != 0:
            peripheral_map[_key] = camera_list[_key]

    for _key in controller_list.keys():
        if controller_list[_key] != 0:
            peripheral_map[_key] = controller_list[_key]

    for _key in display_list.keys():
        if display_list[_key] != 0:
            peripheral_map[_key] = display_list[_key]
    if debug:
        for _key in peripheral_map.keys():
            logging.info('---device : %s, %d', _key, peripheral_map[_key])

    return peripheral_map


def check_peripherals_for_cfm(peripheral_map):
    """
    Check CfM has one and only one camera,
    one and only one speaker,
    or one and only one mimo.
    @param peripheral_map: dict for connected camera, speaker, or mimo.
    @returns: True if check passes,
              False if check fails.
    """
    peripherals = peripheral_map.keys()

    type_camera = set(peripherals).intersection(get_usb_devices.CAMERA_LIST)
    type_speaker = set(peripherals).intersection(get_usb_devices.SPEAKER_LIST)
    type_controller = set(peripherals).intersection(\
                      get_usb_devices.TOUCH_CONTROLLER_LIST)
    type_panel = set(peripherals).intersection(\
                 get_usb_devices.TOUCH_DISPLAY_LIST)

    # check CfM have one, and only one type camera, huddly and mimo
    if len(type_camera) == 0:
        logging.info('No camera is found on CfM.')
        return False

    if not len(type_camera) == 1:
        logging.info('More than one type of cameras are found on CfM.')
        return False

    if len(type_speaker) == 0:
        logging.info('No speaker is found on CfM.')
        return False

    if not len(type_speaker) == 1:
        logging.info('More than one type of speakers are found on CfM.')
        return False

    if len(type_controller) == 0:
       logging.info('No controller is found on CfM.')
       return False


    if not len(type_controller) == 1:
        logging.info('More than one type of controller are found on CfM.')
        return False

    if len(type_panel) == 0:
        logging.info('No Display is found on CfM.')
        return False

    if not len(type_panel) == 1:
        logging.info('More than one type of displays are found on CfM.')
        return False

    # check CfM have only one camera, huddly and mimo
    for _key in peripheral_map.keys():
        if peripheral_map[_key] > 1:
            logging.info('Number of device %s connected to CfM : %d',
                         peripheral_map[_key])
            return False

    return True


def check_usb_enumeration(dut, puts, debug):
    """
    Check USB enumeration for devices
    @param dut: the handle of CfM under test
    @param puts: the list of peripherals under test
    @param debug: variable to define whether to print out test log
                  to stdout
    @returns True, none if test passes
             False, errMsg if test test fails
    """
    usb_data = retrieve_usb_devices(dut)
    if not usb_data:
        logging.info('No usb devices found on DUT')
        return False, 'No usb devices found on DUT'
    else:
        usb_device_list = extract_peripherals_for_cfm(usb_data, debug)
        if debug:
            logging.info('---usb device = %s', usb_device_list)
        if not set(puts).issubset(set(usb_device_list.keys())):
            logging.info('Detect device fails for usb enumeration')
            logging.info('Expect enumerated devices: %s', puts)
            logging.info('Actual enumerated devices: %s',
                         usb_device_list.keys())
            return False, 'Some usb devices are not found.'
        return True, None


def check_usb_interface_initializion(dut, puts, debug):
    """
    Check CfM shows valid interface for all peripherals connected.
    @param dut: the handle of CfM under test
    @param puts: the list of peripherals under test
    @param debug: variable to define whether to print out test log
                  to stdout
    @returns True, none if test passes
             False, errMsg if test test fails
    """
    usb_data = retrieve_usb_devices(dut)
    for put in puts:
        number, health = get_usb_devices.is_usb_device_ok(usb_data, put)
        if debug:
            logging.info('---device interface = %d, %s for %s',
                         number, health, put)
        if '0' in health:
            logging.info('Device %s has invalid interface', put)
            return False, 'Device %s has invalid interface'.format(put)
    return True, None


def clear_core_file(dut):
    """clear core files"""
    try:
        cmd = "rm -rf /var/spool/crash/*.*"
        dut.run_output(cmd)
    except Exception as e:
        logging.info('Fail to clean core files under '
                     '/var/spool/crash')
        logging.info('Fail to execute %s :', cmd)


def check_process_crash(dut, cdlines, debug):
    """Check whether there is core file."""
    try:
        cmd = 'ls -latr /var/spool/crash '
        core_files_output = dut.run_output(cmd).splitlines()
        if debug:
            logging.info('---%s\n---%s', cmd, core_files_output)
        if len(core_files_output) - cdlines <= 0:
            if debug:
                logging.info('---length of files: %d', len(core_files_output))
            return True, len(core_files_output)
        else:
            return False, len(core_files_output)
    except Exception as e:
        if debug:
            logging.info('WARNING: can not find file under /var/spool/crash.')
            logging.info('Fail to execute %s :', cmd)
        return True,  CORE_DIR_LINES


def gpio_usb_test(dut, gpio_list, device_list, pause, board, debug):
    """
    Run GPIO test to powercycle usb port.
    @parama dut: handler of CfM,
    @param gpio_list: the list of gpio ports,
    @param device_list: the list of usb devices,
    @param pause: time needs to wait before restoring power to usb port,
                  in seconds
    @param board: board name for CfM
    @param debug: if True print out status of test progress,
                  else, don't print it out.
    @returns True
    """
    if not gpio_list:
       gpio_list = []
       for device in device_list:
           vid, pid  = device.split(':')
           if debug:
               logging.info('---check gpio for device %s:%s', vid, pid)
           try:
               ports = power_cycle_usb_util.get_target_all_gpio(dut, board, \
                                                            vid , pid)
               [gpio_list.append(_port) for _port in ports]
           except Exception as e:
               errmsg = 'Fail to get gpio port'
               logging.info('%s.', errmsg)
               return False, errmsg

    for port in gpio_list:
        if not port:
            continue
        if debug:
            logging.info('+++powercycle gpio port %s', port)
        try:
            power_cycle_usb_util.power_cycle_usb_gpio(dut, \
                     port, pause)
        except Exception as e:
            errmsg = 'Fail to powercycle gpio port'
            logging.info('%s.', errmsg)
            return False, errmsg
    return True, None


def reboot_test(dut, pause):
    """
    Reboot CfM.
    @parama dut: handler of CfM,
    @param pause: time needs to wait after issuing reboot command, in seconds,

    """
    try:
        dut.reboot()
        logging.info('---reboot done')
        time.sleep(pause)
        return True
    except Exception as e:
        logging.info('Fail to reboot CfM')
        return False


def find_last_log(dut, speaker, debug):
    """
    Get the lastlast_lines line for log files.
    @param dut: handler of CfM
    @param speaker: vidpid if speaker.
    @param debug: if True print out cli output, otherwise not.
    @returns: the list of string of the last line of logs.
    """
    last_lines = {
              'messages':[],
              'chrome':[],
              'ui': [],
              'atrus': []
                  }
    if debug:
        logging.info('\n\nGet the last line of log file, speaker %s', speaker)
    try:
        cmd = "tail -1 /var/log/messages | awk -v N=1 '{print $N}'"
        last_lines['messages'] = dut.run_output(cmd)
        cmd = "tail -1 /var/log/chrome/chrome | awk -v N=1 '{print $N}'"
        last_lines['chrome'] = dut.run_output(cmd)
        cmd = "tail -1 /var/log/ui/ui.LATEST | awk -v N=1 '{print $N}'"
        last_lines['ui']= dut.run_output(cmd)
        if speaker == ATRUS and check_is_platform(dut, 'guado', debug):
            if debug:
                logging.info('---atrus speaker %s connected to CfM', speaker)
            cmd = "tail -1 /var/log/atrus.log | awk -v N=1 '{print $N}'"
            last_lines['atrus'] = dut.run_output(cmd)
    except Exception as e:
        logging.info('Fail to get the last line from log files')
    if debug:
        for key in last_lines.keys():
            logging.info('---%s, %s', key, last_lines[key])
    return last_lines


def collect_log_since_last_check(dut, lastlines, logfile, debug):
    """Collect log file since last check."""
    if logfile == "messages":
        cmd ='awk \'/{}/,0\' /var/log/messages'.format(lastlines[logfile])
    if logfile == "chrome":
        cmd ='awk \'/{}/,0\' /var/log/chrome/chrome'.format(lastlines[logfile])
    if logfile == "ui":
        cmd ='awk \'/{}/,0\' /var/log/ui/ui.LATEST'.format(lastlines[logfile])
    if logfile == 'atrus':
         cmd ='awk \'/{}/,0\' /var/log/atrus.log'.format(lastlines[logfile])
    if debug:
        logging.info('---cmd = %s', cmd)
    try:
        output =  dut.run_output(cmd).split('\n')
        if debug:
            logging.info('---length of log: %d', len(output))
        if not output:
            if debug:
                logging.info('--fail to find match log, check the latest log.')
    except Exception as e:
        logging.info('Fail to get output from log files %d', len(output))
    if not output:
        if logfile == "messages":
            cmd ='cat /var/log/messages'
        if logfile == "chrome":
            cmd ='cat /var/log/chrome/chrome'
        if logfile == "ui":
            cmd ='cat /var/log/ui/ui.LATEST'
        if logfile == 'atrus':
            cmd ='cat /var/log/atrus.log'
        output =  dut.run_output(cmd).split('\n')
        if debug:
            logging.info('---length of log: %d', len(output))
    return output

def check_log(dut, timestamp, error_list, checkitem, logfile, debug):
    """
    Check logfile does not contain any element in error_list[checkitem].
    """
    error_log_list = []
    if debug:
        logging.info('---now check log %s in file %s', checkitem, logfile)
    output = collect_log_since_last_check(dut, timestamp, logfile, debug)
    for _error in error_list[checkitem]:
         matched_line = [s for s in output if _error in str(s)]
         error_log_list = error_log_list + matched_line
         if debug:
             if _error in output:
                 logging.info('---Detected error:%s, log file: %s',
                              _error, logfile)
    if not error_log_list:
        return True, None
    else:
        if debug:
            for _error_line in error_log_list:
                logging.info('---Error log:  %s', _error_line)
        return False, 'Found error in log.'
