# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging, re, subprocess, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


# Expected output of 'tpm_version' command
TPM_VERSION = {
    'TPM 1.2 Version Info': '',
    'Chip Version': '1.2.19.18',
    'Spec Level': '2',
    'Errata Revision': '2',
    'TPM Vendor ID': 'IFX\x00',
    'Vendor Specific data': '1312000f 00',
    'TPM Version': '01010000',
    'Manufacturer Info': '49465800',
    }

# List of acceptable stdout of running 'tpm_selftest' command
TPM_SELFTEST_GOOD = [
    'TPM Test Results: bfbff5bf ff8f',
    ]

# List of acceptable stderr of running 'tpm_selftest' command
TPM_SELFTEST_FAIL = [
    ('Tspi_TPM_SelfTestFull failed: 0x00000026 - layer=tpm, code=0026 (38), '
    'Invalid POST init sequence'),
    ]

# I2C constants
I2C_BUS = '2'
PCA9555_INT = '39'
INA219B1_INT = '64'
INA219B2_INT = '68'
I2CSET_CMD = 'i2cset'
I2CGET_CMD = 'i2cget'
YES_FLAG = '-y'
BYTE_MODE = 'b'
WORD_MODE = 'w'


def callI2Cproc(args, rc_list=[]):
    """Run a command in subprocess and return stdout.

    Args:
      args: a list of string, command to run.
      rc_list: a list of int, acceptable returncode values.

    Returns:
      out: a string, stdout of the command executed.
      err: a string, stderr of the command executed, or None.

    Raises:
      RuntimeError, if process return code is non-zero.
    """
    # Sleep for 1 second so we don't overwhelm I2C bus with too many commands
    time.sleep(1)
    logging.debug('callI2Cproc args = %r; rc_list = %r', args, rc_list)
    proc = subprocess.Popen(args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    logging.error('callI2Cproc %s: out=%r, err=%r', args[0], out, err)
    if proc.returncode and proc.returncode not in rc_list:
        raise RuntimeError('callI2Cproc %s failed with returncode %d: %s' %
                           (args[0], proc.returncode, out))
    return str(out), str(err)


def enableI2C():
    """Enable i2c-dev so i2c-tools can be used.

    Raises:
      TestFail error if i2c-dev can't be enabled.
    """
    args = ['i2cdetect', '-l']
    out, _ = callI2Cproc(args)
    if not out:
        logging.info('i2c-dev disabled. Enabling it with modprobe')
        out, _ = callI2Cproc(['modprobe', 'i2c-dev'])
        if out:
            raise error.TestFail('Error enable i2c-dev: %s' % out)
        out, _ = callI2Cproc(args)
    logging.info('i2c-dev ready to go:\n%s', out)


def initializePCA9555():
    """Initialize PCA9555 module on the TCCI devices.

    For more info: http://www.lm-sensors.org/wiki/man/i2cset

    Raises:
      TestFail error, if error scanning an I2C address for PCA9555.
    """
    base_args = [I2CSET_CMD, YES_FLAG, I2C_BUS, PCA9555_INT]
    args_list = [['2', '65407', WORD_MODE],
                 ['4', '0', WORD_MODE],
                 ['6', '49159', WORD_MODE]]
    for i in args_list:
        out, _ = callI2Cproc(base_args + i)
        if out:
            raise error.TestFail('Error initialize PCA9555: %s' % out)


def initializeINA219B():
    """Initialize TTCI I2C devices.

    Raises:
      TestFail error, if error scanning a specified I2C address.
    """
    base_args = [I2CSET_CMD, YES_FLAG, I2C_BUS]
    # Initialize INA219B #1 (Backup Power Measurement)
    args_list = [[INA219B1_INT, '0', '40753', WORD_MODE],
                 [INA219B1_INT, '5', '51470', WORD_MODE]]
    for i in args_list:
        out, _ = callI2Cproc(base_args + i)
        if out:
            raise error.TestFail('Error initialize INA219B #1 address: %s' %
                                 out)
    # Initialize INA219B #2 (Main Power Measurement)
    args_list = [[INA219B2_INT, '0', '40753', WORD_MODE],
                 [INA219B2_INT, '5', '51470', WORD_MODE]]
    for i in args_list:
        out, _ = callI2Cproc(base_args + i)
        if out:
            raise error.TestFail('Error initialize INA219B #2 address: %s' %
                                 out)


def activateLEDs():
    """Activate each of the feedback LEDs in sequence.

    Raises:
      TestFail error, if any command fails.
    """
    base_args = [I2CSET_CMD, YES_FLAG, I2C_BUS, PCA9555_INT]
    args_list = [(0, ['3', '254', BYTE_MODE]),
                 (1, ['3', '253', BYTE_MODE]),
                 (2, ['3', '251', BYTE_MODE]),
                 (3, ['3', '247', BYTE_MODE]),
                 (4, ['3', '239', BYTE_MODE]),
                 (5, ['3', '223', BYTE_MODE]),
                 ('PP', ['2', '65535', WORD_MODE]),
                 ('ALL', ['2', '49407', WORD_MODE])]
    for (k, v) in args_list:
        out, _ = callI2Cproc(base_args + v)
        if out:
            raise error.TestFail('Error activate LED %s: %s' % (k, out))


def deactivateLEDs():
    """Deactivate all LEDS.

    Raises:
      TestFail error, if failure deactivating LEDs.
    """
    out, _ = callI2Cproc([I2CSET_CMD, YES_FLAG, I2C_BUS, PCA9555_INT, '2',
                          '65407', WORD_MODE])
    if out:
        raise error.TestFail('Error deactivate LEDs: %s' % out)


def readInput(address, register, expect=None):
    """Read digital input.

    Args:
      address: a string, bus address value in decimal.
      register: a string, register number.
      expect: a string (hex value), expected value.

    Returns:
      a string, stdout value or None.

    Raises:
      TestFail error if actual value differs from expected value.
    """
    out, _ = callI2Cproc([I2CGET_CMD, YES_FLAG, I2C_BUS, address, register,
                          WORD_MODE])
    if expect is None:
        return out
    if not out or out.strip() != expect:
        raise error.TestFail('Error read input: expected=%s, actual=%s' %
                             (expect, out))
    return None


def computeVoltage(volt, p):
    """Performs voltage calculation.

    Args:
      volt: a string (hex value).
      p: a Python Regular Expression Pattern object.

    Returns:
      a float, voltage value.
    """
    if not p.match(volt):
        raise error.TestFail(
            'Error: voltage string %s does not match expected pattern' % volt)
    # Swap low and high bytes of response
    swap = ''.join([volt[0:2], volt[4:6], volt[2:4]])
    try:
        decimal = int(swap, 16)
        return decimal/2000.0
    except ValueError, e:
        raise error.TestFail('Error convert voltage value %s: %s' % (volt, e))


def checkVoltageRange(p, address):
    """Reads voltage value and checks if it falls within a pre-specified range.

    Args:
      p: a Python Regular Expression Pattern object.
      address: a string, bus address value in decimal.

    Raises:
      TestFail error if val doesn't fall in range.
    """
    volt_hex = readInput(address, '2')
    volt_float = computeVoltage(volt_hex, p)
    if volt_float < 3.25 or volt_float > 3.35:
        raise error.TestFail('Voltage value %r out of range [3.25, 3.35]' %
                             volt_float)
    # TODO(tgao): report power voltage


def validateTpmVersion(p):
    """Validates output of tpm_version command.

    Args:
      p: a Python Regular Expression Pattern object.

    Raises:
      TestFail error, if output of tpm_version doesn't match TPM_VERSION.
    """
    out, _ = callI2Cproc(['tpm_version'])
    if not out:
        raise error.TestFail('Error request tpm_version')

    d = dict()
    for i in out.splitlines():
        m = p.match(i)
        if not m:
            logging.warn('line %r does not match pattern. Skipped', i)
            continue
        d[m.group(1)] = m.group(2)
    if d != TPM_VERSION:
        raise error.TestFail(
            'Error tpm_version output mismatch: expected=%r, actual=%r' %
            (TPM_VERSION, d))


def controlTpmTraffic(val):
    """Control I2C traffic to TPM.

    Args:
      val: a string (int value), valid values are '127' (enable),
           '119' (disable), '63' (hardware reset).
    """
    out, _ = callI2Cproc([I2CSET_CMD, YES_FLAG, I2C_BUS, PCA9555_INT, '2', val,
                          BYTE_MODE])
    if out:
        raise error.TestFail('Error control I2C traffic to TPM: %r' % out)


def computeTimeElapsed(end, start):
    """Computes time difference in microseconds.

    Args:
      end: a datetime.datetime() object, end timestamp.
      start: a datetime.datetime() object, start timestamp.

    Returns:
      usec: an int, difference between end and start in microseconds.
    """
    t = end - start
    usec = 1000000 * t.seconds + t.microseconds
    logging.info('Elapsed time = %d usec', usec)
    return usec


def runTpmSelfTest(expect_err=False):
    """Runs tpm_selftest command.

    Args:
      expect_err: a boolean, True == check stderr of tpm_selftest command and
                  False == check stdout of the command.

    Raises:
      TestFail error, if actual value is missing or unexpected.
    """
    start_time = datetime.datetime.now()
    if expect_err:
        out, err = callI2Cproc(['tpm_selftest'], rc_list=[255])
    else:
        out, _ = callI2Cproc(['tpm_selftest'])
    end_time = datetime.datetime.now()
    _ = computeTimeElapsed(end_time, start_time)
    # TODO(tgao): report execution time for self test
    if expect_err:
        if not err:
            raise error.TestFail('Error execute tpm_selftest: expected stderr '
                                 'but found none')
        actual = err
        expect = TPM_SELFTEST_FAIL
    else:
        if not out:
            raise error.TestFail('Error execute tpm_selftest: expected stdout '
                                 'but found none')
        actual = out
        expect = TPM_SELFTEST_GOOD

    actual = actual.strip()
    if actual not in expect:
        raise error.TestFail(
            'Error tpm_selftest output mismatch: expected=%r, actual=%r' %
            (expect, actual))


class hardware_TPMI2ctools(test.test):
    version = 1

    def setup(self):
        enableI2C()

    def run_once(self):
        # Initialize modules on TTCI board
        initializePCA9555()
        initializeINA219B()

        # Check LEDs on TTCI board
        activateLEDs()
        readInput(PCA9555_INT, '0', '0x00ff')
        deactivateLEDs()
        readInput(PCA9555_INT, '0', '0x3f7b')

        # Check Backup and Main Power of INA219B module
        voltage_pattern = re.compile('^0x([0-9a-f]{4,4})$')
        checkVoltageRange(voltage_pattern, INA219B1_INT)
        checkVoltageRange(voltage_pattern, INA219B2_INT)

        # Request and validate TPM version info
        line_pattern = re.compile('^\s*([^:]+):\s*(.*)$')
        validateTpmVersion(line_pattern)
        # TODO(tgao): report tpm version info

        # Disable I2C traffic to TPM module
        controlTpmTraffic('119')
        # TPM version info should be unavailable
        out, _ = callI2Cproc(['tpm_version'], rc_list=[255])
        if out:
            raise error.TestFail('Unexpected tpm_version output: %s' % out)
        # Enable I2C traffic to TPM module
        controlTpmTraffic('127')
        # Verify TPM version info is available again
        validateTpmVersion(line_pattern)
        # TODO(tgao): report tpm_version info

        # Run TPM self test
        runTpmSelfTest()
        # Generate hardware reset signal to TPM module
        controlTpmTraffic('63')
        time.sleep(1)
        # Deactivate hardware reset signal to TPM module
        controlTpmTraffic('127')
        # TPM self test should fail here
        runTpmSelfTest(expect_err=True)
        # Re-initialize PCA9555 module should cause TPM self test to fail
        initializePCA9555()
        runTpmSelfTest(expect_err=True)
