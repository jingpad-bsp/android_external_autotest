# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gtk
import re
import serial as pyserial
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful

# Modem commands.
DEVICE_NORMAL_RESPONSE = 'OK'
_MESSAGE_PROMPT = (
    'Please insert the SIM card then press enter.\n'
    '請插入SIM卡後按回車鍵\n')


class factory_BasicCellular(test.test):
    version = 5

    def make_decision_widget(self,
                             message,
                             key_action_mapping,
                             fg_color=ful.LIGHT_GREEN):
        '''Returns a widget that display the message and bind proper functions.

        Args:
          message: Message to display on the widget.
          key_action_mapping: A dict of tuples indicates functions and keys
              in the format {gtk_keyval: (function, function_parameters)}

        Returns:
          A widget binds with proper functions.
        '''
        widget = gtk.VBox()
        widget.add(ful.make_label(message, fg=fg_color))
        widget.key_callback = (
            lambda w, e: self._key_action_mapping_callback(
                w, e, key_action_mapping))
        return widget

    def _key_action_mapping_callback(self, widget, event, key_action_mapping):
        if event.keyval in key_action_mapping:
            callback, callback_parameters = key_action_mapping[event.keyval]
            callback(*callback_parameters)
            return True

    def _register_callbacks(self, window):
        def key_press_callback(widget, event):
            self.test_widget.key_callback(widget, event)
            factory.log('calling widget %s' % widget)
        window.connect('key-press-event', key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)

    def run_once(self, imei_re, iccid_re, dev='/dev/ttyUSB0',
                 reset_modem_waiting=0, prompt=False):
        '''Connects to the modem, checking the IMEI and ICCID.

        For the iccid test, please note this test requires a SIM card,
        a test SIM is fine. The SIM does NOT need to have an account
        provisioned.

        @param imei_re: The regular expression of expected IMEI.
                        None value to skip this item.
        @param iccid_re: The regular expression of expected ICCID.
                         None value to skip this item.
        @param dev: Path to the modem. Default to /dev/ttyUSB0.
        @param reset_modem_waiting: Interger greater than zero indicates
                                    a reset command will be issued and
                                    reconnect to modem after
                                    reset_modem_waiting secs.
        @param prompt: True to display a prompt for sim card insertion.
        '''
        if prompt:
            key_action_mapping = {
                gtk.keysyms.Return: (
                    self._run,
                    [imei_re, iccid_re, dev, reset_modem_waiting, prompt])}
            self.test_widget = self.make_decision_widget(
                _MESSAGE_PROMPT, key_action_mapping=key_action_mapping)
            ful.run_test_widget(
                    self.job,
                    self.test_widget,
                    window_registration_callback=self._register_callbacks)
        else:
            self._run(imei_re, iccid_re, dev, reset_modem_waiting, prompt)

    def _run(self, imei_re, iccid_re, dev, reset_modem_waiting, prompt):
        def read_response():
            '''Reads response from the modem until a timeout.'''
            line = serial.readline()
            factory.log('modem[ %r' % line)
            return line.rstrip('\r\n')

        def send_command(command):
            '''Sends a command to the modem and discards the echo.'''
            serial.write(command + '\r')
            factory.log('modem] %r' % command)
            echo = read_response()

        def check_response(expected_re):
            '''Reads response and checks with a regular expression.'''
            response = read_response()
            if not re.match(expected_re, response):
                raise error.TestError(
                    'Expected %r but got %r' % (expected_re, response))

        try:
            # Kill off modem manager, which might be holding the device open.
            utils.system("stop modemmanager", ignore_status=True)

            serial = pyserial.Serial(dev, timeout=2)
            serial.read(serial.inWaiting())  # Empty the buffer.

            if reset_modem_waiting > 0:
                # Reset the modem.
                send_command('AT+CFUN=6')
                check_response(DEVICE_NORMAL_RESPONSE)
                serial.close()
                time.sleep(reset_modem_waiting)
                # Reconnect to the modem
                serial = pyserial.Serial(dev, timeout=2)
                serial.read(serial.inWaiting())

            # Send an AT command and expect 'OK'
            send_command('AT')
            check_response(DEVICE_NORMAL_RESPONSE)

            # Check IMEI.
            if imei_re is not None:
                send_command('AT+CGSN')
                check_response(imei_re)
                check_response('')
                check_response(DEVICE_NORMAL_RESPONSE)

            # Check ICCID.
            if iccid_re is not None:
                send_command('AT+ICCID')
                check_response(iccid_re)
                check_response('')
                check_response(DEVICE_NORMAL_RESPONSE)
        finally:
            try:
                # Restart the modem manager.
                utils.system("start modemmanager", ignore_status=True)
            except Exception as e:
                factory.log('Exception - %s' % e)
        if prompt:
            gtk.main_quit()
