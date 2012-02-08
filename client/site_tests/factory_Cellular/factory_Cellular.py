# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import logging
import os
import re
import select
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

from autotest_lib.client.cros import factory
from autotest_lib.client.cros.rf import agilent_scpi
from autotest_lib.client.cros.rf import lan_scpi
from autotest_lib.client.cros.rf import modem_commands
from autotest_lib.client.cros.rf.config import PluggableConfig


# See http://niviuk.free.fr/umts_band.php for band calculations.
base_config = PluggableConfig({
    'tx_channels': [
        # band_name, channel, freq, min_power, max_power
        ('WCDMA_IMT_BC1',   9750, 1950.0e6,  3.5,  5.5),
        ('WCDMA_1900_BC2',  9400, 1880.0e6,    4,    8),
        ('WCDMA_800_BC5',   4180,  836.0e6, 13.5, 17.5),
        #('WCDMA_900_BC8',   2787,  897.4e6,    0,    0),
    ],
    'rx_channels': [
        ('WCDMA_800', 4405, 881e6, -55, -40),
    ],
})


class factory_Cellular(test.test):
    version = 1

    def run_once(self, ext_host, dev='ttyUSB0', config_path=None):
        config = base_config.Read(config_path)

        # TODO(jsalz): Disable and re-enable ModemManager, and reset the modem
        # at the end of the test.

        ext = agilent_scpi.EXTSCPI(ext_host, timeout=5)
        logging.info('Tester ID: %s' % ext.id)

        modem = open('/dev/%s' % dev, 'rb+', 0)

        # TODO(jsalz): Use pyserial instead
        def ReadLine(timeout=2):
            '''
            Reads a line from the modem with the given timeout.

            Returns the line, without leading or trailing whitespace.
            '''
            chars = []
            start = time.time()
            while True:
                if chars and chars[-1] == '\n':
                    logging.debug('modem[ %r' % ''.join(chars))
                    return ''.join(chars).strip()

                if timeout:
                    remaining = start + timeout - time.time()
                    if remaining <= 0:
                        raise utils.TimeoutError()
                else:
                    remaining = None

                ready, _, _ = select.select([modem], [], [], remaining)
                if not ready:
                    raise utils.TimeoutError()
                char = modem.read(1)
                if char == '':
                    raise EOFError()
                chars.append(char)

        def SendLine(line):
            '''
            Sends a line to the modem.
            '''
            logging.debug('modem] %r' % line)
            modem.write(line + '\r')

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
        SendCommand(modem_commands.ENABLE_FACTORY_TEST_MODE)
        ExpectLine('OK')

        failures = []

        tx_power_by_channel = {}

        # Start continuous transmit
        for (band_name, channel, freq,
             min_power, max_power) in config['tx_channels']:
            channel_id = (band_name, channel)

            SendCommand(modem_commands.START_TX_TEST % (band_name, channel))
            ExpectLine(modem_commands.START_TX_TEST_RESPONSE)
            ExpectLine('')
            ExpectLine('OK')

            # Get channel power from the EXT
            power = ext.MeasureChannelPower('WCDMA', freq, port=ext.PORTS.RFIO1)
            tx_power_by_channel[channel_id] = power
            if power < min_power or power > max_power:
                failures.append(
                    'Power for channel %s is %g, out of range (%g,%g)' %
                    (channel_id, power, min_power, max_power))

        logging.info("TX power: %s" % [
                (k, tx_power_by_channel[k])
                for k in sorted(tx_power_by_channel.keys())])

        rx_power_by_channel = {}

        for (band_name, channel, freq,
             min_power, max_power) in config['rx_channels']:
            channel_id = (band_name, channel)

            ext.EnableSource('WCDMA', freq, port=ext.PORTS.RFIO1)
            # Try a few times, as it may take the modem a while to pick up the
            # new RSSI
            power_readings = []
            def IsPowerInRange():
                SendCommand(modem_commands.READ_RSSI % (band_name, channel))
                line = ReadLine()
                match = re.match(modem_commands.READ_RSSI_RESPONSE, line)
                if not match:
                    raise error.TestError(
                        'Expected RSSI value but got %r' % line)
                power = int(match.group(1))
                power_readings.append(power)
                if power >= min_power and power <= max_power:
                    return power
                ExpectLine('')
                ExpectLine('OK')

            try:
                utils.poll_for_condition(IsPowerInRange,
                                         timeout=5, sleep_interval=0.5)
            except utils.TimeoutError:
                failures.append(
                    'RSSI on %s out of range (%g, %g); read %s' % (
                        channel_id, min_power, max_power, power_readings))

            rx_power_by_channel[channel_id] = power_readings[-1]

        logging.info("RX power: %s" % [
                (k, rx_power_by_channel[k])
                for k in sorted(rx_power_by_channel.keys())])

        if failures:
            raise error.TestError('; '.join(failures))
