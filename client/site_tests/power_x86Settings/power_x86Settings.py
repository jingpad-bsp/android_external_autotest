# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, os, re, commands
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import power_status


# Specify registers to check.  The format needs to be:
#   register offset : ('bits', 'expression')
DMI_BAR_CHECKS = {
    'cpuA': {
        '0x88':  [('1:0', 3)],
        '0x200': [('27:26', 0)],
        '0x210': [('2:0', 1), ('15:8', 1)],
        '0xc28': [('5:1', 7)],
        '0xc2e': [('5', 1)],
        '0xc30': [('11', 0), ('10:8', 4)],
        '0xc34': [('9:4', 7), ('0', 1)],
        },
    'cpuB': {},
    }

MCH_BAR_CHECKS = {}

MSR_CHECKS = {
    'cpuA': {
        '0xe2':  [('7', 0), ('2:0', 4)],
        '0x198': [('28:24', 6)],
        '0x1a0': [('33:32', 3), ('26:25', 3), ('16', 1)],
        },
    'cpuB': {
        # IA32_ENERGY_PERF_BIAS[3:0] -- 0 == hi-perf, 6 balanced, 15 powersave
        '0x1b0': [('3:0', 6)],
        },
    }

# Give an ASPM exception for these PCI devices. ID is taken from lspci -n.
ASPM_EXCEPTED_DEVICES = {
    'cpuA': [
        # Intel 82801G HDA Controller
        '8086:27d8'
        ],
    'cpuB': [
        # Intel HDA Controller
        '8086:1c20'
        ],
    }

GFX_CHECKS = {
    'cpuB': {'i915_enable_rc6': 1, 'i915_enable_fbc': 1, 'powersave': 1,
             'semaphores':1 }
    }


SUBTESTS = ['dmi', 'mch', 'msr', 'pcie_aspm', 'wifi', 'usb', 'storage',
            'audio', 'filesystem', 'graphics']


class power_x86Settings(test.test):
    version = 1

    def run_once(self):
        if not self._check_cpu_type():
            raise error.TestNAError('Unsupported CPU')

        self._rdmsr_cmd = 'iotools rdmsr 0'
        self._pci_read32_cmd = 'iotools pci_read32'
        self._mmio_read32_cmd = 'iotools mmio_read32'

        status = power_status.get_status()
        if status.linepower[0].online:
            logging.info('AC Power is online')
            self._on_ac = True
        else:
            logging.info('AC Power is offline')
            self._on_ac = False

        failures = ''

        for testname in SUBTESTS:
            logging.info("SUBTEST = %s", testname)
            func = getattr(self, "_verify_%s_power_settings" % testname)
            fail_count = func()
            if fail_count:
                failures += '%s_failures(%d) ' % (testname, fail_count)

        if failures:
            raise error.TestFail(failures)


    def _check_cpu_type(self):
        cpuinfo = utils.read_file('/proc/cpuinfo')

        # Look for Intel Atom N4xx or N5xx series CPUs
        if re.search(r'Intel.*Atom.*N[45]', cpuinfo):
            self._cpu_type = 'cpuA'
            return True
        if re.search(r'Intel.*Celeron.*8[1456][07]', cpuinfo):
            self._cpu_type = 'cpuB'
            return True
        if re.search(r'Intel.*Core.*i[357]-2[357][0-9][0-9]', cpuinfo):
            self._cpu_type = 'cpuB'
            return True

        logging.info(cpuinfo)
        return False


    def _verify_wifi_power_settings(self):
        if self._on_ac:
            expected_state = 'off'
        else:
            expected_state = 'on'

        iwconfig_out = utils.system_output('iwconfig 2>&1', retain_output=True)
        match = re.search(r'Power Management:(.*)', iwconfig_out)
        if match and match.group(1) == expected_state:
            return 0

        logging.info(iwconfig_out)
        return 1


    def _verify_storage_power_settings(self):
        if self._on_ac:
            return 0

        expected_state = 'min_power'

        dirs_path = '/sys/class/scsi_host/host*'
        dirs = glob.glob(dirs_path)
        if not dirs:
            logging.info('scsi_host paths not found')
            return 1

        for dirpath in dirs:
            link_policy_file = os.path.join(dirpath,
                                            'link_power_management_policy')
            if not os.path.exists(link_policy_file):
                logging.debug('path does not exist: %s', link_policy_file)
                continue

            out = utils.read_one_line(link_policy_file)
            logging.debug('storage: path set to %s for %s',
                           out, link_policy_file)
            if out == expected_state:
                return 0

        return 1


    def _verify_usb_power_settings(self):
        if self._on_ac:
            expected_state = 'on'
        else:
            expected_state = 'auto'

        dirs_path = '/sys/bus/usb/devices/*/power'
        dirs = glob.glob(dirs_path)
        if not dirs:
            logging.info('USB power path not found')
            return 1

        errors = 0
        for dirpath in dirs:
            level_file = os.path.join(dirpath, 'level')
            if not os.path.exists(level_file):
                logging.info('USB: power level file not found for %s', dir)
                continue

            out = utils.read_one_line(level_file)
            logging.debug('USB: path set to %s for %s',
                           out, level_file)
            if out != expected_state:
                errors += 1
                logging.error("Error(%d), %s == %s, but expected %s", errors,
                              level_file, out, expected_state)

        return errors


    def _verify_audio_power_settings(self):
        path = '/sys/module/snd_hda_intel/parameters/power_save'
        out = utils.read_one_line(path)
        logging.debug('Audio: %s = %s', path, out)
        power_save_timeout = int(out)

        # Make sure that power_save timeout parameter is zero if on AC.
        if self._on_ac:
            if power_save_timeout == 0:
                return 0
            else:
                logging.debug('Audio: On AC power but power_save = %d', \
                                                            power_save_timeout)
                return 1

        # Make sure that power_save timeout parameter is non-zero if on battery.
        elif power_save_timeout > 0:
            return 0

        logging.debug('Audio: On battery power but power_save = %d', \
                                                            power_save_timeout)
        return 1


    def _verify_filesystem_power_settings(self):
        mount_output = commands.getoutput('mount | fgrep commit=').split('\n')
        if len(mount_output) == 0:
            logging.debug('No file system entries with commit intervals found.')
            return 1

        errors = 0
        # Parse for 'commit' param
        for line in mount_output:
            try:
                commit = int(re.search(r'(commit=)([0-9]*)', line).group(2))
            except:
                errors += 1
                logging.error('Error(%d), reading commit value from \'%s\'',
                              errors, line)
                continue

            # Check for the correct commit interval.
            if commit != 600:
                errors += 1
                logging.error('Error(%d), incorrect commit interval %d', errors,
                              commit)

        return errors


    def _verify_graphics_power_settings(self):
        """Verify that power-saving for graphics are configured properly.

        Returns:
            0 if no errors, otherwise the number of errors that occurred.
        """
        errors = 0

        if self._cpu_type in GFX_CHECKS:
            checks = GFX_CHECKS[self._cpu_type]
            for param_name in checks:
                param_path = '/sys/module/i915/parameters/%s' % param_name
                if not os.path.exists(param_path):
                    errors += 1
                    logging.error('Error(%d), %s not found', errors, param_path)
                else:
                    out = utils.read_one_line(param_path)
                    logging.debug('Graphics: %s = %s', param_path, out)
                    value = int(out)
                    if value != checks[param_name]:
                        errors += 1
                        logging.error('Error(%d), %s = %d but should be %d',
                                      errors, param_path, value,
                                      checks[param_name])

        return errors


    def _verify_pcie_aspm_power_settings(self):
        errors = 0
        out = utils.system_output('lspci -n')
        for line in out.splitlines():
            slot, _, pci_id = line.split()[0:3]
            slot_out = utils.system_output('lspci -s %s -vv' % slot,
                                            retain_output=True)
            match = re.search(r'LnkCtl:(.*);', slot_out)
            if match:
                if pci_id in ASPM_EXCEPTED_DEVICES[self._cpu_type]:
                    continue

                split = match.group(1).split()
                if split[1] == 'Disabled' or \
                   (split[2] == 'Enabled' and split[1] != 'L1'):
                    errors += 1
                    logging.info(slot_out)
                    logging.error('Error(%d), %s ASPM off or no L1 support',
                                  errors, slot)
            else:
                logging.info('PCIe: LnkCtl not found for %s', line)

        return errors


    def _verify_dmi_power_settings(self):
        # DMIBAR is at offset 0x68 of B/D/F 0/0/0
        cmd = '%s 0 0 0 0x68' % (self._pci_read32_cmd)
        self._dmi_bar = int(utils.system_output(cmd), 16) & 0xfffffffe
        logging.debug('DMI BAR is %s', hex(self._dmi_bar))

        return self._verify_registers('dmi', self._read_dmi_bar,
                                      DMI_BAR_CHECKS[self._cpu_type])


    def _verify_mch_power_settings(self):
        # MCHBAR is at offset 0x48 of B/D/F 0/0/0
        cmd = '%s 0 0 0 0x48' % (self._pci_read32_cmd)
        self._mch_bar = int(utils.system_output(cmd), 16) & 0xfffffffe
        logging.debug('MCH BAR is %s', hex(self._mch_bar))

        return self._verify_registers('mch', self._read_mch_bar,
                                       MCH_BAR_CHECKS)


    def _verify_msr_power_settings(self):
        return self._verify_registers('msr', self._read_msr,
                                      MSR_CHECKS[self._cpu_type])


    def _verify_registers(self, reg_type, read_fn, match_list):
        errors = 0
        for k, v in match_list.iteritems():
            r = read_fn(k)
            for item in v:
                good = self._shift_mask_match(r, item)
                if not good:
                    errors += 1
                    logging.error('Error(%d), %s: reg = %s val = %s match = %s',
                                  errors, reg_type, k, hex(r), v)
        return errors


    def _shift_mask_match(self, value, match):
        expr = match[1]
        bits = match[0].split(':')
        hi_bit = int(bits[0])
        if len(bits) == 2:
            lo_bit = int(bits[1])
        else:
            lo_bit = int(bits[0])

        value >>= lo_bit
        mask = (1 << (hi_bit - lo_bit + 1)) - 1
        value &= mask

        good = (value == expr)
        if not good:
            logging.info('FAILED: bits = %s value = %s mask = %s expr = %s',
                          bits, hex(value), mask, expr)
        return good


    def _read_dmi_bar(self, offset):
        return self._read_mmio_read32(self._dmi_bar + int(offset, 16))


    def _read_mch_bar(self, offset):
        return self._read_mmio_read32(self._mch_bar + int(offset, 16))


    def _read_mmio_read32(self, address):
        cmd = '%s %s' % (self._mmio_read32_cmd, address)
        return int(utils.system_output(cmd), 16)


    def _read_msr(self, register):
        cmd = '%s %s' % (self._rdmsr_cmd, register)
        return int(utils.system_output(cmd), 16)
