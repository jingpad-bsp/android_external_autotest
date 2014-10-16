# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import os
import re
import subprocess
import threading
import time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

POSITION_X_VALUATOR = '0'
POSITION_Y_VALUATOR = '1'
POSITION_VALUATORS = [POSITION_X_VALUATOR, POSITION_Y_VALUATOR]
PROPERTY_EVENT = 'PropertyEvent'
TOUCH_BEGIN_EVENT = 'RawTouchBegin'
TOUCH_END_EVENT = 'RawTouchEnd'
TOUCH_UPDATE_EVENT = 'RawTouchUpdate'
TOUCH_EVENTS = [TOUCH_BEGIN_EVENT, TOUCH_END_EVENT, TOUCH_UPDATE_EVENT]


class platform_EvdevSynDropTest(test.test):
    """Test SYN_DROPPED event handling in xf86-input-evdev.

    When there is a SYN_DROPPED seen in xf86-input-evdev driver, it tries to
    sync with the kernel evdev state and injects finger arriving, finger
    leaving or axes update events accordingly to make sure upper layer
    (such as X server) is seamless of SYN_DROPPED event. The test mainly
    focuses on testing finger arriving and leaving events generated in
    SYN_DROPPED handling.

    Currently we have four basic SYN_DROPPED tests to be performed :
        a. Finger leaving, i.e., tracking id changes from a non-negative
            number to -1 after SYN_DROPPED.
        b. Finger arriving, i.e., tracking id changes from -1 to a
            non-negative number.
        c. Finger changing, i.e., original finger leaving and new finger
            arriving, tracking id changes from a non-negative number to
            another one.
        d. Same finger, but axes change, i.e., no tracking id changes, but some
            axes values have changed.

    For each test case, a pre-recorded event log is chopped into four
    pieces:

        1. original finger set
        2. finger events(leaving/arriving) to be dropped due to queue full
        3. events playbacked to push xinput events out
        4. cleanup events

    After playing-back the first piece, we block the evdev event reading in
    order to generate SYN_DROPPED when we inject the second piece of events.
    Then, we unblock the evdev event reading and inject the third piece of
    events to collect the finger leaving/arriving XI2 events. These XI2
    events could be used to verify if SYN_DROPPED handling is processed
    correctly.
    """
    version = 1

    def setUp(self):
        self.stop_parser = False
        self.syndrop_detected = False
        self.stop_xi2_parser = False
        self.finger_set = {}

        utils.assert_has_X_server()
        os.environ['DISPLAY'] = ':0'
        os.environ['XAUTHORITY'] = '/home/chronos/.Xauthority'
        self.data_dir = os.path.join(self.bindir, 'data')
        device_file = os.path.join(self.data_dir, 'device')
        self.device_ready = threading.Event()
        self.dev_emu_proc = subprocess.Popen(['evemu-device', device_file],
                                             stdout=subprocess.PIPE)
        self.device_id = self.get_evemu_device_id(self.dev_emu_proc)
        self.device = '/dev/input/event' + self.device_id

        # Xorg log parser for detection of SYN_DROPPED
        self.xlog_parser_thread = threading.Thread(target=self.xlog_parser)
        self.xlog_parser_thread.start()

        # Wait until the device is available in X server
        self.device_ready.wait()

        # xinput 2 event parser for finger tracking above xf86-input-evdev
        self.xi2_parser_ready = threading.Event()
        self.xi2_proc = subprocess.Popen(['stdbuf', '-o0', 'xinput', 'test-xi2',
                                          self.device_id],
                                         stdout=subprocess.PIPE)
        self.xi2_parser_thread = threading.Thread(target=self.xi2_parser,
                                                  args=(self.xi2_proc,))
        self.xi2_parser_thread.start()

        # Wait until XI2 parser is ready
        self.xi2_parser_ready.wait()

    def tearDown(self):
        self.dev_emu_proc.kill()
        self.xi2_proc.kill()
        self.stop_parser = True
        self.xlog_parser_thread.join()
        self.stop_xi2_parser = True
        self.xi2_parser_thread.join()

    def xi2_parser(self, proc):
        event_type = 0
        self.position = {}
        while not self.stop_xi2_parser:
            line = proc.stdout.readline()
            if not self.xi2_parser_ready.is_set():
                if re.search('Reporting', line):
                    self.xi2_parser_ready.set()
            # EVENT type 23 (RawTouchUpdate)
            type_line = re.match('EVENT\stype\s\d+\s\((\w+)\)', line)
            if type_line:
                event_type = type_line.group(1)
                if event_type == PROPERTY_EVENT:
                    self.finger_set = {}
            if event_type in TOUCH_EVENTS:
                detail = re.match('\s+detail:\s(\d+)', line)
                if detail:
                    finger_id = detail.group(1)
                    if event_type not in self.finger_set.keys():
                        self.finger_set[event_type] = []
                    if finger_id not in self.finger_set[event_type]:
                        self.finger_set[event_type].append(finger_id)
                # For valuators
                #   0: 1902.00 (1902.00)
                valuator = re.match('\s+(\d+):\s(\d+.\d+)\s+\(\d+.\d+\)', line)
                if valuator and valuator.group(1) in POSITION_VALUATORS:
                    self.position[valuator.group(1)] = valuator.group(2)

    def xlog_parser(self):
        log = open('/var/log/Xorg.0.log', 'r')
        log.seek(0, 2)
        while not self.stop_parser:
            line = log.readline()
            if not line:
                time.sleep(0.001)
                continue
            if not self.device_ready.is_set():
                if re.search('ChromeOS-MT-Device:\sSync_State:', line):
                    self.device_ready.set()
            if re.match('[^\+]+\++\sSYN_DROPPED\s\++', line):
                self.syndrop_detected = True

    def get_evemu_device_id(self, proc):
        output = proc.stdout.readline()
        match = re.match('[^ ]+\s\/dev\/input\/event(\d+)', output)
        return match.group(1)

    def test_condition(self, condition=None):
        # Inject the original finger events
        step1 = open(os.path.join(self.data_dir, condition + '.1'), 'r')
        subprocess.call(['evemu-play', self.device], stdin=step1)

        self.original_set = copy.deepcopy(self.finger_set)

        # Blocking xf86-input-evdev event reading
        step2 = open(os.path.join(self.data_dir, condition + '.2'), 'r')
        subprocess.call(['xinput', 'set-prop', self.device_id,
                         'Block Event Reading', '1'])

        # Inject events to fill up the evdev queue to generate SYN_DROPPED
        subprocess.call(['evemu-play', self.device], stdin=step2)

        # Unblock xf86-input-evdev event processing
        step3 = open(os.path.join(self.data_dir, condition + '.3'), 'r')
        subprocess.call(['xinput', 'set-prop', self.device_id,
                         'Block Event Reading', '0'])
        subprocess.call(['evemu-play', self.device], stdin=step3)

        # Check if SYN_DROPPED event is seen in Xorg.0.log
        if not self.syndrop_detected:
            raise error.TestError('Did not see SYN_DROPPED event')

        # Store the finger event seen in xinput after SYN_DROPPED
        self.syndrop_set = copy.deepcopy(self.finger_set)

        # Store the latest position valuators especially for test case (d)
        self.syndrop_position = copy.deepcopy(self.position)

        # Continue on injecting remaining events for cleanup
        step4 = open(os.path.join(self.data_dir, condition + '.4'), 'r')
        subprocess.call(['evemu-play', self.device], stdin=step4)

    def verify_finger_leaving(self):
        """Verify if finger leaving event is injected after SYN_DROPPED.

        Suppose there are two fingers with tracking id '1' and '2' in the
        beginning. Finger '2' leaves after SYN_DROPPED, then we should get
        the finger sets in xi2_parser:
            original_set:
                {'RawTouchBegin': ['1', '2'], 'RawTouchUpdate': ['1', '2']}
            syndrop_set:
                {'RawTouchEnd': ['2'], 'RawTouchUpdate': ['1']}
        """
        syndrop_end_set = set(self.syndrop_set[TOUCH_END_EVENT])
        syndrop_update_set = set(self.syndrop_set[TOUCH_UPDATE_EVENT])
        union = syndrop_end_set | syndrop_update_set
        intersection = syndrop_end_set & syndrop_update_set
        if union != set(self.original_set[TOUCH_BEGIN_EVENT]):
            raise error.TestFail('The union should include both fingers')
        if intersection:
            raise error.TestFail('The intersection of the set should be empty')

    def verify_finger_arriving(self):
        """Verify if finger arriving event is injected after SYN_DROPPED.

        Suppose there is only one finger with tracking id '3' in the
        beginning. Finger '4' appears after SYN_DROPPED, then we should get
        the finger sets in xi2_parser:
            original_set:
                {'RawTouchBegin': ['3'], 'RawTouchUpdate': ['3']}
            syndrop_set:
                {'RawTouchBegin': ['4'], 'RawTouchUpdate': ['3', '4']}
        """
        original_begin_set = set(self.original_set[TOUCH_BEGIN_EVENT])
        syndrop_begin_set = set(self.syndrop_set[TOUCH_BEGIN_EVENT])
        union = original_begin_set | syndrop_begin_set
        intersection = original_begin_set & syndrop_begin_set
        if union != set(self.syndrop_set[TOUCH_UPDATE_EVENT]):
            raise error.TestFail('The union should include both fingers')
        if intersection:
            raise error.TestFail('The intersection of the set should be empty')

    def verify_finger_changing(self):
        """Verify if finger changing events are injected after SYN_DROPPED.

        Suppose there are two fingers with tracking id '5' and '6' in the
        beginning. Finger '6' leaves and Finger '7' appears after
        SYN_DROPPED, then we should get the finger sets in xi2_parser:
            original_set:
                {'RawTouchBegin': ['5', '6'], 'RawTouchUpdate': ['5', '6']}
            syndrop_set:
                {'RawTouchEnd': ['6'], 'RawTouchBegin': ['7'],
                 'RawTouchUpdate': ['5', '7']}
        """
        original_update_set = set(self.original_set[TOUCH_UPDATE_EVENT])
        syndrop_update_set = set(self.syndrop_set[TOUCH_UPDATE_EVENT])
        finger_leaving = original_update_set - syndrop_update_set
        if not finger_leaving:
            raise error.TestFail('One original finger should disappear')
        if finger_leaving != set(self.syndrop_set[TOUCH_END_EVENT]):
            raise error.TestFail('Should see finger leaving event')

        finger_arriving = syndrop_update_set - original_update_set
        if not finger_arriving:
            raise error.TestFail('One new finger should arrive')
        if finger_arriving != set(self.syndrop_set[TOUCH_BEGIN_EVENT]):
            raise error.TestFail('Should see finger arriving event')

    def verify_same_finger(self):
        """Verify if finger position are updated after SYN_DROPPED.

        Suppose there is one finger in the beginning. Between block reading
        event in step 2 and unblock reading event in step3, the finger moves
        to (1897, 725). And there is no POSITION_X and POSITION_Y update in
        step 3. The test is to verify the position should be updated with
        (1897, 725) in xi2_parser after SYN_DROPPED.
        """
        if self.syndrop_position[POSITION_X_VALUATOR] != '1897.00':
            raise error.TestFail('Incorrect POSITION_X after SYN_DROPPED')
        if self.syndrop_position[POSITION_Y_VALUATOR] != '725.00':
            raise error.TestFail('Incorrect POSITION_Y after SYN_DROPPED')

    def run_once(self):
        self.setUp()
        self.test_condition('finger_leaving')
        self.tearDown()
        self.verify_finger_leaving()

        self.setUp()
        self.test_condition('finger_arriving')
        self.tearDown()
        self.verify_finger_arriving()

        self.setUp()
        self.test_condition('finger_changing')
        self.tearDown()
        self.verify_finger_changing()

        self.setUp()
        self.test_condition('same_finger')
        self.tearDown()
        self.verify_same_finger()
