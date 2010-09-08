# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, hashlib, logging, os, pprint, re, sys
from autotest_lib.client.bin import factory
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import flashrom_util
from autotest_lib.client.common_lib import gbb_util
from autotest_lib.client.common_lib import site_vblock


class hardware_Components(test.test):
    version = 1
    _cids = [
        'hash_ro_firmware',
        'part_id_audio_codec',
        'part_id_cpu',
        'part_id_display_panel',
        'part_id_embedded_controller',
        'part_id_ethernet',
        'part_id_flash_chip',
        'part_id_hwqual',
        'part_id_storage',
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
        'part_id_cardreader',
        'part_id_webcam',
        'part_id_3g',
        'part_id_gps',
    ]
    _check_existence_cids = [
        'key_recovery',
        'key_root',
        'part_id_chrontel',
    ]
    _non_check_cids = [
        'data_bitmap_fv',
        'data_display_geometry',
        'data_recovery_url',
    ]
    _not_present = 'Not Present'


    def check_component(self, comp_key, comp_id):
        if comp_key in self._ignored:
            return

        self._system[comp_key] = [ comp_id ]

        if not self._approved.has_key(comp_key):
            raise error.TestFail('%s missing from database' % comp_key)

        app_cids = self._approved[comp_key]

        if '*' in app_cids:
            return

        if not comp_id in app_cids:
            self._failures[comp_key] = [ comp_id ]


    def check_approved_part_id_existence(self, cid, type):
        """
        Check if there are matching devices on the system.
        Parameter type should be one of 'pci', 'usb', or 'others'.
        """
        if cid in self._ignored:
            return

        if not self._approved.has_key(cid):
            raise error.TestFail('%s missing from database' % cid)

        approved_devices = self._approved[cid]
        if '*' in approved_devices:
            self._system[cid] = [ '*' ]
            return

        for device in approved_devices:
            present = False
            if type in ['pci', 'usb']:
                try:
                    cmd = '/usr/sbin/ls' + type + ' -d %s'
                    output = utils.system_output(cmd % device)
                    # If it shows something, means found.
                    if output:
                        present = True
                except:
                    pass
            elif type == 'others':
                present = getattr(self, 'check_existence_' + cid)(device)

            if present:
                self._system[cid] = [ device ]
                return

        self._failures[cid] = [ 'No match' ]


    def check_existence_key_recovery(self, part_id):
        current_key = self._gbb.get_recoverykey()
        target_key = utils.read_file(part_id)
        return current_key == target_key


    def check_existence_key_root(self, part_id):
        current_key = self._gbb.get_rootkey()
        target_key = utils.read_file(part_id)
        return current_key == target_key


    def check_existence_part_id_chrontel(self, part_id):
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


    def get_part_id_audio_codec(self):
        cmd = 'grep -R Codec: /proc/asound/* | head -n 1 | sed s/.\*Codec://'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_cpu(self):
        cmd = 'grep -m 1 \'model name\' /proc/cpuinfo | sed s/.\*://'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_display_panel(self):
        cmd = ('get-edid | parse-edid | grep ModelName | '
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


    def get_part_id_flash_chip(self):
        # example output:
        #  Found chip "Winbond W25x16" (2048 KB, FWH) at physical address 0xfe
        parts = []
        lines = utils.system_output('flashrom', ignore_status=True).split('\n')
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


    def get_part_id_storage(self):
        cmd = ('cd $(find /sys/devices -name sda)/../..; '
               'cat vendor model | tr "\n" " " | sed "s/ \+/ /g"')
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_wireless(self):
        """
          Returns a colon delimited string where the first section
          is the vendor id and the second section is the device id.
        """
        part_id = utils.read_one_line('/sys/class/net/wlan0/device/device')
        vendor_id = utils.read_one_line('/sys/class/net/wlan0/device/vendor')
        return "%s:%s" % (vendor_id.replace('0x',''), part_id.replace('0x',''))


    def get_vendor_id_touchpad(self):
        cmd = 'grep -i Touchpad /proc/bus/input/devices | sed s/.\*=//'
        part_id = utils.system_output(cmd).strip('"')
        return part_id


    def get_vendor_id_webcam(self):
        cmd = 'cat /sys/class/video4linux/video0/name'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_hash_ro_firmware(self):
        """
        Returns a hash of Read Only firmware parts,
        to confirm we have proper keys / boot code / recovery image installed.
        """
        # hash_ro_list: RO section to be hashed
        hash_ro_list = ['FV_BSTUB', 'FV_GBB', 'FVDEV']
        flashrom = flashrom_util.flashrom_util()
        if not flashrom.select_bios_flashrom():
            raise error.TestError('Cannot select BIOS flashrom')
        base_img = flashrom.read_whole()
        flashrom_size = len(base_img)
        # XXX we can NOT trust base image here for layout, otherwise firmware
        # can provide fake (non-used) GBB/BSTUB in garbage area.
        layout = flashrom.detect_chromeos_bios_layout(flashrom_size, None)
        if not layout:
            raise error.TestError('Cannot detect ChromeOS flashrom layout')
        hash_src = ''
        for section in hash_ro_list:
            src = flashrom.get_section(base_img, layout, section)
            if not src:
                raise error.TestError('Cannot get section [%s] from flashrom' %
                                      section)
            hash_src = hash_src + src
        if not hash_src:
            raise error.TestError('Invalid hash source from flashrom.')
        return hashlib.sha256(hash_src).hexdigest()


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
            block = site_vblock.unpack_verification_block(data)
            ver = block['VbFirmwarePreambleHeader']['firmware_version']
            versions[index] = ver
        # we embed error reports in return value.
        assert len(versions) == 2
        if versions[0] != versions[1]:
            return 'A=%d, B=%d' % (versions[0], versions[1])
        return '%d' % (versions[0])


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


    def initialize(self):
        self._gbb = gbb_util.GBBUtility()
        self._pp = pprint.PrettyPrinter()


    def run_once(self, approved_dbs='approved_components', ignored_cids=[],
            shared_dict={}):
        self._ignored = ignored_cids
        only_cardreader_failed = False
        all_failures = 'The following components are not matched.\n'
        os.chdir(self.bindir)

        # If found the HwQual ID in shared_dict, use the list with the same ID.
        if 'part_id_hwqual' in shared_dict:
            id = shared_dict['part_id_hwqual']
            id = id.rpartition(' ')[0].replace(' ', '_')
            approved_dbs = 'qualified_components*%s' % id

        # approved_dbs supports shell-like filename expansion.
        for db in glob.iglob(approved_dbs):
            self._system = {}
            self._failures = {}

            if not os.path.exists(db):
                raise error.TestError('Unable to find approved db: %s' % db)

            self._approved = eval(utils.read_file(db))
            logging.debug('Approved DB: %s', self.pformat(self._approved))

            for cid in self._cids:
                self.check_component(cid, self.force_get_property('get_' + cid))

            for cid in self._pci_cids:
                self.check_approved_part_id_existence(cid, type='pci')

            for cid in self._usb_cids:
                self.check_approved_part_id_existence(cid, type='usb')

            for cid in self._check_existence_cids:
                self.check_approved_part_id_existence(cid, type='others')

            logging.debug('System: %s', self.pformat(self._system))

            outdb = os.path.join(self.resultsdir, 'system_components')
            utils.open_write_close(outdb, self.pformat(self._system))

            if self._failures:
                if self._failures.keys() == ['part_id_cardreader']:
                    only_cardreader_failed = True
                all_failures += 'For DB %s:' % db
                all_failures += self.pformat(self._failures)
            else:
                # If one of DBs is matched, record some data in shared_dict.
                cids_need_to_be_record = ['part_id_hwqual']
                for cid in cids_need_to_be_record:
                    factory.log_shared_data(cid, self._approved[cid][0])
                return

        if only_cardreader_failed:
            all_failures = ('You may forget to insert an SD card.\n' +
                            all_failures)

        raise error.TestFail(all_failures)
