# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import logging
import os
import re
import select
import time

import serial

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import leds
from autotest_lib.client.cros.rf import agilent_scpi
from autotest_lib.client.cros.rf import lan_scpi
from autotest_lib.client.cros.rf import rf_utils
from autotest_lib.client.cros.rf.config import PluggableConfig


# See http://niviuk.free.fr/umts_band.php for band calculations.
base_config = PluggableConfig({
    'tx_channels': [
        # band_name, channel, freq, min_power, max_power
        ('WCDMA_IMT_BC1',   9750, 1950.0e6,  7.6,  9.6),
        ('WCDMA_1900_BC2',  9400, 1880.0e6,    4,    8),
        ('WCDMA_800_BC5',   4180,  836.0e6, 13.5, 17.5),
        #('WCDMA_900_BC8',   2787,  897.4e6,    0,    0),
    ],
    'rx_channels': [
        ('WCDMA_800', 4405, 881e6, -55, -40),
    ],
})


# Modem commands.
ENABLE_FACTORY_TEST_MODE_COMMAND = 'AT+CFUN=5'
DISABLE_FACTORY_TEST_MODE_COMMAND = 'AT+CFUN=1'

START_TX_TEST_COMMAND = 'AT+ALLUP="%s",%d,"on",75'
START_TX_TEST_RESPONSE = 'ALLUP: ON'

READ_RSSI_COMMAND = 'AT+AGC="%s",%d,"%s"'
READ_RSSI_RESPONSE = r'RSSI: ([-\d]+)'


class factory_Cellular(test.test):
    version = 1

    def run_once(self, ext_host, dev='ttyUSB0', config_path=None,
                 use_rfio2_for_aux=False,
                 set_interface_ip=None):
        if set_interface_ip:
            rf_utils.SetInterfaceIp(*set_interface_ip)

        with leds.Blinker(((leds.LED_NUM|leds.LED_CAP, 0.25),
                           (leds.LED_CAP|leds.LED_SCR, 0.25))):
            self._run(ext_host, dev, config_path, use_rfio2_for_aux)

    def _run(self, ext_host, dev, config_path, use_rfio2_for_aux):
        config = base_config.Read(config_path)

        # Kill off modem manager, which might be holding the device open.
        utils.system("stop modemmanager", ignore_status=True)

        ext = agilent_scpi.EXTSCPI(ext_host, timeout=5)
        logging.info('Tester ID: %s' % ext.id)

        ser = serial.Serial('/dev/%s' % dev, timeout=2)

        def ReadLine():
            '''
            Reads a line from the modem.
            '''
            line = ser.readline()
            logging.debug('modem[ %r' % line)
            return line.rstrip('\r\n')

        def SendLine(line):
            '''
            Sends a line to the modem.
            '''
            logging.debug('modem] %r' % line)
            ser.write(line + '\r')

        def SendCommand(command):
            '''
            Sends a line to the modem and discards the echo.
            '''
            SendLine(command)
            echo = ReadLine()

        def ExpectLine(expected_line):
            '''
            Expects a line from the modem.
            '''
            line = ReadLine()
            if line != expected_line:
                raise error.TestError(
                    'Expected %r but got %r' % (expected_line, line))

        # Send an AT command; expect an echo and ignore the response
        SendLine('AT')
        for _ in range(2):
            try:
                ReadLine()
            except utils.TimeoutError:
                pass

        # Send an AT command and expect 'OK'
        SendCommand('AT')
        ExpectLine('OK')

        # Put in factory test mode
        try:
            SendCommand(ENABLE_FACTORY_TEST_MODE_COMMAND)
            ExpectLine('OK')

            failures = []

            tx_power_by_channel = {}

            # Start continuous transmit
            for (band_name, channel, freq,
                 min_power, max_power) in config['tx_channels']:
                channel_id = (band_name, channel)

                def StartTxTest():
                    SendCommand(START_TX_TEST_COMMAND % (band_name, channel))
                    line = ReadLine()
                    if 'restricted to FTM' in line:
                        logging.info('Factory test mode not ready: %r' % line)
                        return False
                    return True

                # This may fail the first time if the modem isn't ready;
                # try a few more times.
                utils.poll_for_condition(
                    StartTxTest, timeout=5, sleep_interval=0.5,
                    desc='Start TX test')

                ExpectLine('')
                ExpectLine('OK')

                # Get channel power from the EXT
                power = ext.MeasureChannelPower('WCDMA', freq,
                                                port=ext.PORTS.RFIO1)
                tx_power_by_channel[channel_id] = power
                if power < min_power or power > max_power:
                    failures.append(
                        'Power for channel %s is %g, out of range (%g,%g)' %
                        (channel_id, power, min_power, max_power))

            logging.info("TX power: %s" % [
                    (k, tx_power_by_channel[k])
                    for k in sorted(tx_power_by_channel.keys())])

            rx_power_by_channel = {}

            for antenna, port in (
                ('MAIN', ext.PORTS.RFIO1),
                ('AUX',
                 ext.PORTS.RFIO2 if use_rfio2_for_aux else ext.PORTS.RFIO1)):
                for (band_name, channel, freq,
                     min_power, max_power) in config['rx_channels']:
                    channel_id = (band_name, channel)

                    ext.EnableSource('WCDMA', freq, port=port)
                    # Try a few times, as it may take the modem a while to pick
                    # up the new RSSI
                    power_readings = []
                    def IsPowerInRange():
                        SendCommand(READ_RSSI_COMMAND % (
                                band_name, channel, antenna))
                        line = ReadLine()
                        match = re.match(READ_RSSI_RESPONSE,
                                         line)
                        if not match:
                            raise error.TestError(
                                'Expected RSSI value but got %r' % line)
                        power = int(match.group(1))
                        power_readings.append(power)
                        ExpectLine('')
                        ExpectLine('OK')
                        if power >= min_power and power <= max_power:
                            return power

                    try:
                        utils.poll_for_condition(IsPowerInRange,
                                                 timeout=5, sleep_interval=0.5)
                    except utils.TimeoutError:
                        failures.append(
                            'RSSI for %s/%s out of range (%g, %g); read %s' % (
                                antenna, channel_id,
                                min_power, max_power, power_readings))

                    rx_power_by_channel[antenna, channel_id] = (
                        power_readings[-1])

            logging.info("RX power: %s" % [
                    (k, rx_power_by_channel[k])
                    for k in sorted(rx_power_by_channel.keys())])

            if failures:
                raise error.TestError('; '.join(failures))
        finally:
            SendCommand(DISABLE_FACTORY_TEST_MODE_COMMAND)
