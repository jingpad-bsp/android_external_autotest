# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, pprint, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class hardware_Components(test.test):
    version = 1
    _cids = [
        'part_id_audio_codec',
        'part_id_bios',
        'part_id_cpu',
        'part_id_embedded_controller',
        'part_id_ethernet',
        'part_id_flash_chip',
        'part_id_storage',
        'part_id_wireless',
        'vendor_id_touchpad',
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
    ]
    _not_present = 'Not Present'


    def check_component(self, comp_key, comp_id):
        self._system[comp_key] = [ comp_id ]

        if not self._approved.has_key(comp_key):
            raise error.TestFail('%s missing from database' % comp_key)

        app_cids = self._approved[comp_key]

        if '*' in app_cids:
            return

        if not comp_id in app_cids:
            self._failures[comp_key] = [ comp_id ]


    def get_part_id_audio_codec(self):
        cmd = 'grep -R Codec: /proc/asound/* | head -n 1 | sed s/.\*Codec://'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_bios(self):
        cmd = ('dmidecode | grep -A 2 "BIOS Information" | tail -2 '
               '| sed "s/.*: //" | tr "\n" " "')
        part_id = utils.system_output(cmd).strip()

        cmd = ('dmidecode | grep "\(BIOS\|Firmware\) Revision" | sed "s/\t//" '
               '| sed "s/Revision/Rev/"')
        rev_num = ', '.join(utils.system_output(cmd).split('\n'))

        if rev_num:
            part_id = part_id + ' (' + rev_num + ')'

        return part_id


    def get_part_id_cpu(self):
        cmd = 'grep -m 1 \'model name\' /proc/cpuinfo | sed s/.\*://'
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
          match = re.search(r'Found chip "(.*)" .* at physical address ', line)
          if match:
            parts.append(match.group(1))
        part_id = ", ".join(parts)
        return part_id


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


    def check_approved_part_id_existence(self, cid, type):
        """
        Check if there are matching vendor_id:product_id pairs on the PCI or
        USB. Parameter type should be either 'pci' or 'usb'.
        """
        cmd = 'sudo /usr/sbin/ls' + type + ' -d %s'
        if not self._approved.has_key(cid):
            raise error.TestFail('%s missing from database' % cid)

        approved_devices = self._approved[cid]
        if '*' in approved_devices:
            self._system[cid] = [ '*' ]
            return

        for device in approved_devices:
            try:
                output = utils.system_output(cmd % device)
                # If it shows something, means found.
                if output:
                  self._system[cid] = [ device ]
                  return
            except:
                pass
        self._failures[cid] = [ 'No match' ]


    def get_vendor_id_touchpad(self):
        cmd = 'grep -i Touchpad /proc/bus/input/devices | sed s/.\*=//'
        part_id = utils.system_output(cmd).strip('"')
        return part_id


    def get_vendor_id_webcam(self):
        cmd = 'cat /sys/class/video4linux/video0/name'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def pformat(self, obj):
        return "\n" + self._pp.pformat(obj) + "\n"


    def initialize(self):
        self._pp = pprint.PrettyPrinter()


    def run_once(self, approved_db='approved_components'):
        self._system = {}
        self._failures = {}

        approved_db = os.path.join(self.bindir, approved_db)
        if not os.path.exists(approved_db):
            raise error.TestError('Unable to find approved_db: %s' %
                                  approved_db)

        self._approved = eval(utils.read_file(approved_db))
        logging.debug('Approved DB: %s', self.pformat(self._approved))

        for cid in self._cids:
            self.check_component(cid, getattr(self, 'get_' + cid)())

        for cid in self._pci_cids:
            self.check_approved_part_id_existence(cid, type='pci')

        for cid in self._usb_cids:
            self.check_approved_part_id_existence(cid, type='usb')

        logging.debug('System: %s', self.pformat(self._system))

        outdb = os.path.join(self.resultsdir, 'system_components')
        utils.open_write_close(outdb, self.pformat(self._system))

        if self._failures:
            raise error.TestFail(self.pformat(self._failures))
