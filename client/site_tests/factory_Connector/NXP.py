# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


'''
Protocols for NXP SC18IM700.
'''

import logging
import serial
import sys
import time


# I2C address mask.
WRITE_MASK = 0xFE
READ_MASK = 0xFF

# Constants for I2C status register.
I2C_OK = 0b11110000
I2C_NACK_ON_ADDRESS = 0b11110001
I2C_NACK_ON_DATA = 0b11110011
I2C_TIME_OUT = 0b11111000
I2C_STATUS = [I2C_OK, I2C_NACK_ON_ADDRESS, I2C_NACK_ON_DATA, I2C_TIME_OUT]

SEC_WAIT_I2C = 0.05


class SC18IM700(object):
    '''
    Wrapped class for communicating with NXP-SC18IM700.
    '''
    def __init__(self, device_path):
        '''Connects to NXP via serial port.

        @param device_path: The device path of serial port.
        '''
        self.logger = logging.getLogger('SC18IM700')
        self.logger.debug('Setup serial device... [%s]' % device_path)
        self.ser = serial.Serial(port=device_path,
                                 baudrate=9600,
                                 bytesize=serial.EIGHTBITS,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE,
                                 xonxoff=False,
                                 rtscts=True,
                                 interCharTimeout=1)
        self.logger.debug('pySerial [%s] configuration : %s' % (
                          serial.VERSION, self.ser.__repr__()))

    def _write(self, data):
        '''Converts data to bytearray and writes to the serial port.'''
        self.ser.write(bytearray(data))
        self.ser.flush()

    def _read(self):
        '''Reads data from serial port(Non-Blocking).'''
        ret = self.ser.read(self.ser.inWaiting())
        self.logger.debug('Hex and binary dump of datas - ')
        for char in ret:
            self.logger.debug('  %x - %s' % (ord(char), bin(ord(char))))
        return ret

    @staticmethod
    def _slave_addr_write(slave_addr_7bits):
        '''Converts slave_addr from 7 bits to 8 bits with a write mask.'''
        return (slave_addr_7bits << 1) & WRITE_MASK

    @staticmethod
    def _slave_addr_read(slave_addr_7bits):
        '''Converts slave_addr from 7 bits to 8 bits with a read mask.'''
        return (slave_addr_7bits << 1) & READ_MASK

    def read_i2c_bus_status(self):
        '''Returns the I2C bus status.'''
        cmd = [ord('R'), 0x0A, ord('P')]
        self._write(cmd)
        time.sleep(SEC_WAIT_I2C)
        ret = self._read()
        if (len(ret) == 1) and (ord(ret[0]) in I2C_STATUS):
            return ord(ret[0])
        raise Exception("I2C_STATUS_READ_FAILED")

    def send_i2c(self, slave_addr, int_array, status_check=True):
        '''Sends data to I2C slave device.

        @param slave_addr: The address of slave in 7bits format.
        @param int_array: The data to send in integer array.
        @param status_check: Whether to check I2C bus status.

        @return: An integer indicates I2C status if required.
        '''
        cmd = ([ord('S'),
               self._slave_addr_write(slave_addr),
               len(int_array)] +
               int_array +
               [ord('P')])
        self._write(cmd)

        if status_check:
            return self.read_i2c_bus_status()
