# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import firmware_hash
import glob
import logging
import os
import pprint
import re
from autotest_lib.client.bin import factory
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import flashrom_util, gbb_util, vblock


class hardware_Components(test.test):
    version = 2
    # We divide all component IDs (cids) into 5 categories:
    #  - enumable: able to get the results by running specific commands;
    #  - PCI: PCI devices;
    #  - USB: USB devices;
    #  - probable: returns existed or not by given some pre-defined choices;
    #  - not test: only data, don't test them.
    _enumerable_cids = [
        'data_display_geometry',
        'hash_ec_firmware',
        'hash_ro_firmware',
        'part_id_audio_codec',
        'part_id_cpu',
        'part_id_display_panel',
        'part_id_dram',
        'part_id_embedded_controller',
        'part_id_ethernet',
        'part_id_flash_chip',
        'part_id_ec_flash_chip',
        'part_id_hwqual',
        'part_id_keyboard',
        'part_id_storage',
        'part_id_tpm',
        'part_id_wireless',
        'vendor_id_touchpad',
        'version_rw_firmware',
    ]
    _pci_cids = [
        'part_id_chipset',
        'part_id_usb_hosts',
        'part_id_vga',
    ]
    _usb_cids = [
        'part_id_bluetooth',
        'part_id_webcam',
        'part_id_3g',
        'part_id_gps',
    ]
    _probable_cids = [
        'key_recovery',
        'key_root',
        'part_id_cardreader',
        'part_id_chrontel',
    ]
    _not_test_cids = [
        'data_bitmap_fv',
        'data_recovery_url',
    ]
    _to_be_tested_cids_groups = [
        _enumerable_cids,
        _pci_cids,
        _usb_cids,
        _probable_cids,
    ]
    _not_present = 'Not Present'


    def get_all_enumerable_components(self):
        results = {}
        for cid in self._enumerable_cids:
            components = self.force_get_property('get_' + cid)
            if not isinstance(components, list):
                components = [ components ]
            results[cid] = components
        return results


    def get_all_pci_components(self):
        cmd = 'lspci -n | cut -f3 -d" "'
        return utils.system_output(cmd).split()


    def get_all_usb_components(self):
        cmd = 'lsusb | cut -f6 -d" "'
        return utils.system_output(cmd).split()


    def check_enumerable_component(self, cid, exact_values, approved_values):
        if '*' in approved_values:
            return

        for value in exact_values:
            if value not in approved_values:
                if cid in self._failures:
                    self._failures[cid].append(value)
                else:
                    self._failures[cid] = [ value ]


    def check_pci_usb_component(self, cid, system_values, approved_values):
        if '*' in approved_values:
            self._system[cid] = [ '*' ]
            return

        for value in approved_values:
            if value in system_values:
                self._system[cid] = [ value ]
                return

        self._failures[cid] = [ 'No match' ]


    def check_probable_component(self, cid, approved_values):
        if '*' in approved_values:
            self._system[cid] = [ '*' ]
            return

        for value in approved_values:
            present = getattr(self, 'probe_' + cid)(value)
            if present:
                self._system[cid] = [ value ]
                return

        self._failures[cid] = [ 'No match' ]


    def get_data_display_geometry(self):
        # Get edid from driver. TODO(nsanders): this is driver specific.
        # TODO(waihong): read-edid is also x86 only.
        cmd = 'find /sys/devices/ -name edid | grep LVDS'
        edid_file = utils.system_output(cmd)

        cmd = ('cat ' + edid_file + ' | parse-edid | grep "Mode " | '
               'sed \'s/^.*"\(.*\)".*$/\\1/\'')
        data = utils.system_output(cmd).split()
        if not data:
            data = [ '' ]
        return data


    def get_hash_ec_firmware(self):
        """
        Returns a hash of Embedded Controller firmware parts,
        to confirm we have proper updated version of EC firmware.
        """
        return firmware_hash.get_ec_hash(exception_type=error.TestError)


    def get_hash_ro_firmware(self):
        """
        Returns a hash of Read Only (BIOS) firmware parts,
        to confirm we have proper keys / boot code / recovery image installed.
        """
        return firmware_hash.get_bios_ro_hash(exception_type=error.TestError)


    def get_part_id_audio_codec(self):
        cmd = 'grep -R Codec: /proc/asound/* | head -n 1 | sed s/.\*Codec://'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_cpu(self):
        cmd = 'grep -m 1 \'model name\' /proc/cpuinfo | sed s/.\*://'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_display_panel(self):
        cmd = 'find /sys/devices/ -name edid | grep LVDS'
        edid_file = utils.system_output(cmd)

        cmd = ('cat ' + edid_file + ' | parse-edid | grep ModelName | '
               'sed \'s/^.*ModelName "\(.*\)"$/\\1/\'')
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_embedded_controller(self):
        # example output:
        #  Found Nuvoton WPCE775x (id=0x05, rev=0x02) at 0x2e
        parts = []
        res = utils.system_output('superiotool', ignore_status=True).split('\n')
        for line in res:
            match = re.search(r'Found (.*) at', line)
            if match:
                parts.append(match.group(1))
        part_id = ", ".join(parts)
        return part_id


    def get_part_id_ethernet(self):
        """
          Returns a colon delimited string where the first section
          is the vendor id and the second section is the device id.
        """
        # Ethernet is optional so mark it as not present. A human
        # operator needs to decide if this is acceptable or not.
        vendor_file = '/sys/class/net/eth0/device/vendor'
        part_file = '/sys/class/net/eth0/device/device'
        if os.path.exists(part_file) and os.path.exists(vendor_file):
            vendor_id = utils.read_one_line(vendor_file).replace('0x', '')
            part_id = utils.read_one_line(part_file).replace('0x', '')
            return "%s:%s" % (vendor_id, part_id)
        else:
            return self._not_present


    def get_part_id_dram(self):
        grep_cmd = 'grep i2c_dev /proc/modules'
        i2c_loaded = (utils.system(grep_cmd, ignore_status=True) == 0)
        if not i2c_loaded:
            utils.system('modprobe -r i2c_dev')
        cmd = ('mosys -l memory spd print geometry | '
               'grep size_mb | cut -f2 -d"|"')
        part_id = utils.system_output(cmd).strip()
        if part_id != '':
            return part_id
        else:
            return self._not_present


    def get_part_id_flash_chip(self):
        # example output:
        #  Found chip "Winbond W25x16" (2048 KB, FWH) at physical address 0xfe
        parts = []
        lines = utils.system_output('flashrom -V -p internal:bus=spi',
                                    ignore_status=True).split('\n')
        for line in lines:
            match = re.search(r'Found chip "(.*)" .* at physical address ',
                              line)
            if match:
                parts.append(match.group(1))
        part_id = ", ".join(parts)
        return part_id


    def get_part_id_ec_flash_chip(self):
        # example output:
        #  Found chip "Winbond W25x10" (128 KB, SPI) at physical address ...
        parts = []
        lines = utils.system_output('flashrom -V -p internal:bus=lpc',
                                    ignore_status=True).split('\n')
        # Undo BBS register after call.
        utils.system('flashrom -p internal:bus=spi', ignore_status=True)
        for line in lines:
            match = re.search(r'Found chip "(.*)" .* at physical address ',
                              line)
            if match:
                parts.append(match.group(1))
        part_id = ", ".join(parts)
        return part_id


    def get_part_id_hwqual(self):
        hwid_file = '/sys/devices/platform/chromeos_acpi/HWID'
        if os.path.exists(hwid_file):
            part_id = utils.read_one_line(hwid_file)
            return part_id
        else:
            return self._not_present

    def get_part_id_keyboard(self):
        # VPD value "initial_locale"="en-US" should be listed.
        cmd = 'vpd -i RO_VPD -l | grep \"keyboard_layout\" | cut -f4 -d\'"\' '
        part_id = utils.system_output(cmd).strip()
        if part_id != '':
            return part_id
        else:
            return self._not_present

    def get_part_id_storage(self):
        cmd = ('cd $(find /sys/devices -name sda)/../..; '
               'cat vendor model | tr "\n" " " | sed "s/ \+/ /g"')
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_tpm(self):
        """
        Returns Manufacturer_info : Chip_Version
        """
        cmd = 'tpm_version'
        tpm_output = utils.system_output(cmd)
        tpm_lines = tpm_output.splitlines()
        tpm_dict = {}
        for tpm_line in tpm_lines:
            [key, colon, value] = tpm_line.partition(':')
            tpm_dict[key.strip()] = value.strip()
        part_id = ''
        key1, key2 = 'Manufacturer Info', 'Chip Version'
        if key1 in tpm_dict and key2 in tpm_dict:
            part_id = tpm_dict[key1] + ':' + tpm_dict[key2]
        return part_id


    def get_part_id_wireless(self):
        """
          Returns a colon delimited string where the first section
          is the vendor id and the second section is the device id.
        """
        part_id = utils.read_one_line('/sys/class/net/wlan0/device/device')
        vendor_id = utils.read_one_line('/sys/class/net/wlan0/device/vendor')
        return "%s:%s" % (vendor_id.replace('0x',''), part_id.replace('0x',''))


    def get_closed_vendor_id_touchpad(self, vendor_name):
        """
        Using closed-source method to derive the vendor information
        given the vendor name.
        """
        part_id = ''
        if vendor_name.lower() == 'synaptics':
            detect_program = '/opt/Synaptics/bin/syndetect'
            model_string_str = 'Model String'
            firmware_id_str = 'Firmware ID'
            if os.path.exists(detect_program):
                data = utils.system_output(detect_program, ignore_status=True)
                properties = dict(map(str.strip, line.split('=', 1))
                                  for line in data.splitlines() if '=' in line)
                model = properties.get(model_string_str, 'UnknownModel')
                firmware_id = properties.get(firmware_id_str, 'UnknownFWID')
                # The pattern " on xxx Port" may vary by the detection approach,
                # so we need to strip it.
                model = re.sub(' on [^ ]* [Pp]ort$', '', model)
                # Format: Model #FirmwareId
                part_id = '%s #%s' % (model, firmware_id)
        return part_id


    def get_vendor_id_touchpad(self):
        # First, try to use closed-source method to probe touch pad
        part_id = self.get_closed_vendor_id_touchpad('Synaptics')
        if part_id != '':
            return part_id
        # If the closed-source method above fails to find vendor infomation,
        # try an open-source method.
        else:
            cmd_grep = 'grep -i Touchpad /proc/bus/input/devices | sed s/.\*=//'
            part_id = utils.system_output(cmd_grep).strip('"')
            return part_id


    def get_vendor_id_webcam(self):
        cmd = 'cat /sys/class/video4linux/video0/name'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_version_rw_firmware(self):
        """
        Returns the version of Read-Write (writable) firmware from VBOOT
        section. If A/B has different version, that means this system
        needs a reboot + firmwar update so return value is a "error report"
        in the form "A=x, B=y".
        """
        versions = [None, None]
        section_names = ['VBOOTA', 'VBOOTB']
        flashrom = flashrom_util.flashrom_util()
        if not flashrom.select_bios_flashrom():
            raise error.TestError('Cannot select BIOS flashrom')
        base_img = flashrom.read_whole()
        flashrom_size = len(base_img)
        # we can trust base image for layout, since it's only RW.
        layout = flashrom.detect_chromeos_bios_layout(flashrom_size, base_img)
        if not layout:
            raise error.TestError('Cannot detect ChromeOS flashrom layout')
        for index, name in enumerate(section_names):
            data = flashrom.get_section(base_img, layout, name)
            block = vblock.unpack_verification_block(data)
            ver = block['VbFirmwarePreambleHeader']['firmware_version']
            versions[index] = ver
        # we embed error reports in return value.
        assert len(versions) == 2
        if versions[0] != versions[1]:
            return 'A=%d, B=%d' % (versions[0], versions[1])
        return '%d' % (versions[0])


    def probe_key_recovery(self, part_id):
        current_key = self._gbb.get_recoverykey()
        target_key = utils.read_file(part_id)
        return current_key.startswith(target_key)


    def probe_key_root(self, part_id):
        current_key = self._gbb.get_rootkey()
        target_key = utils.read_file(part_id)
        return current_key.startswith(target_key)


    def probe_part_id_cardreader(self, part_id):
        # A cardreader is always power off until a card inserted. So checking
        # it using log messages instead of lsusb can limit operator-attended.
        # But note that it does not guarantee the cardreader presented during
        # the time of the test.
        [vendor_id, product_id] = part_id.split(':')
        found_pattern = ('New USB device found, idVendor=%s, idProduct=%s' %
                         (vendor_id, product_id))
        cmd = 'grep -qs "%s" /var/log/messages*' % found_pattern
        return utils.system(cmd, ignore_status=True) == 0


    def probe_part_id_chrontel(self, part_id):
        if part_id == self._not_present:
            return True

        if part_id == 'ch7036':
            grep_cmd = 'grep i2c_dev /proc/modules'
            i2c_loaded = (utils.system(grep_cmd, ignore_status=True) == 0)
            if not i2c_loaded:
                utils.system('modprobe i2c_dev')

            probe_cmd = 'ch7036_monitor -p'
            present = (utils.system(probe_cmd, ignore_status=True) == 0)

            if not i2c_loaded:
                utils.system('modprobe -r i2c_dev')
            return present

        return False


    def force_get_property(self, property_name):
        """ Returns property value or empty string on error. """
        try:
            return getattr(self, property_name)()
        except error.TestError as e:
            logging.error("Test error in getting property %s", property_name,
                          exc_info=1)
            return ''
        except:
            logging.error("Exception getting property %s", property_name,
                          exc_info=1)
            return ''


    def pformat(self, obj):
        return "\n" + self._pp.pformat(obj) + "\n"


    def update_ignored_cids(self, ignored_cids):
        for cid in ignored_cids:
            for group in self._to_be_tested_cids_groups:
                if cid in group:
                    group.remove(cid)
                    break
            else:
                raise error.TestError('The ignored cid %s is not defined' % cid)
            self._not_test_cids.append(cid)


    def read_approved_from_file(self, filename):
        approved = eval(utils.read_file(filename))
        for group in self._to_be_tested_cids_groups + [ self._not_test_cids ]:
            for cid in group:
                if cid not in approved:
                    # If we don't have any listing for this type
                    # of part in HWID, it's not required.
                    factory.log('Bypassing unlisted cid %s' % cid)
                    approved[cid] = '*'
        return approved


    def select_correct_dbs(self, approved_dbs):
        os.chdir(self.bindir)
        id_hwqual = None
        try:
            id_hwqual = factory.get_shared_data('part_id_hwqual')
        except Exception, e:
            # hardware_Components may run without factory environment
            factory.log('Failed getting shared data, ignored: %s' % repr(e))
        if id_hwqual:
            # If HwQual ID is already specified, find the list with same ID.
            id_hwqual = id_hwqual.replace(' ', '_')
            approved_dbs = 'data_*/components_%s' % id_hwqual
        else:
            sample_approved_dbs = 'approved_components.default'
            if (not glob.glob(approved_dbs)) and glob.glob(sample_approved_dbs):
                # Fallback to the default (sample) version
                approved_dbs = sample_approved_dbs
                factory.log('Using default (sample) approved component list: %s'
                            % sample_approved_dbs)

        # approved_dbs supports shell-like filename expansion.
        existing_dbs = glob.glob(approved_dbs)
        if not existing_dbs:
            raise error.TestError('Unable to find approved db: %s' %
                                  approved_dbs)

        return existing_dbs


    def initialize(self):
        self._gbb = gbb_util.GBBUtility()
        self._pp = pprint.PrettyPrinter()


    def run_once(self, approved_dbs='approved_components', ignored_cids=[]):
        self.update_ignored_cids(ignored_cids)
        enumerable_system = self.get_all_enumerable_components()
        pci_system = self.get_all_pci_components()
        usb_system = self.get_all_usb_components()

        only_cardreader_failed = False
        all_failures = 'The following components are not matched.\n'
        correct_dbs = self.select_correct_dbs(approved_dbs)
        for db in correct_dbs:
            self._system = enumerable_system
            self._failures = {}
            approved = self.read_approved_from_file(db)
            factory.log('Approved DB: %s' % self.pformat(approved))

            for cid in self._enumerable_cids:
                self.check_enumerable_component(
                        cid, enumerable_system[cid], approved[cid])

            for cid in self._pci_cids:
                self.check_pci_usb_component(cid, pci_system, approved[cid])

            for cid in self._usb_cids:
                self.check_pci_usb_component(cid, usb_system, approved[cid])

            for cid in self._probable_cids:
                self.check_probable_component(cid, approved[cid])

            factory.log('System: %s' % self.pformat(self._system))

            outdb = 'system_%s' % os.path.basename(db).replace('approved_', '')
            outdb = os.path.join(self.resultsdir, outdb)
            utils.open_write_close(outdb, self.pformat(self._system))

            if self._failures:
                if self._failures.keys() == ['part_id_cardreader']:
                    only_cardreader_failed = True
                all_failures += 'For DB %s:' % db
                all_failures += self.pformat(self._failures)
            else:
                # If one of DBs is matched, record some data in shared_data.
                cids_need_to_be_record = ['part_id_hwqual']
                try:
                    for cid in cids_need_to_be_record:
                        factory.set_shared_data(cid, approved[cid][0])
                except Exception, e:
                    # hardware_Components may run without factory environment
                    factory.log('Failed setting shared data, ignored: %s' %
                                repr(e))
                return

        if only_cardreader_failed:
            all_failures = ('You may forget to insert an SD card.\n' +
                            all_failures)

        raise error.TestFail(all_failures)
