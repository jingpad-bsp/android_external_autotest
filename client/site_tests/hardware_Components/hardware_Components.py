# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, pprint, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_ui


class hardware_Components(test.test):
    version = 1
    _cids = [
        'part_id_audio_codec',
        'part_id_bios',
        'part_id_chipset',
        'part_id_cpu',
        'part_id_embedded_controller',
        'part_id_ethernet',
        'part_id_flash_chip',
        'part_id_storage',
        'part_id_usb_hosts',
        'part_id_vga',
        'part_id_wireless',
        'vendor_id_cardreader',
        'vendor_id_touchpad',
    ]
    _usb_cids = [
        'part_id_bluetooth',
        'part_id_webcam',
        'part_id_3g',
    ]

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


    def get_part_id_chipset(self):
        cmd = ('lspci | grep -E "^00:00.0 " | head -n 1 '
               '| sed s/.\*Host\ bridge://')
        part_id = utils.system_output(cmd).strip()
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
        part_id = utils.read_one_line("/sys/class/net/eth0/device/device")
        vendor_id = utils.read_one_line("/sys/class/net/eth0/device/vendor")
        return "%s:%s" % (vendor_id, part_id)


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


    def get_part_id_usb_hosts(self):
        # Enumerates all USB host controllers
        cmd = 'lspci | grep "USB Controller:" | sed s/.\*USB\ Controller://'
        part_ids = [l.strip() for l in utils.system_output(cmd).split('\n')]
        part_id = ", ".join(part_ids)
        return part_id


    def get_part_id_vga(self):
        cmd = ('lspci | grep "VGA compatible controller:" | head -n 1 '
               '| sed s/.\*VGA\ compatible\ controller://')
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_wireless(self):
        """
          Returns a colon delimited string where the first section
          is the vendor id and the second section is the device id.
        """
        part_id = utils.read_one_line("/sys/class/net/wlan0/device/device")
        vendor_id = utils.read_one_line("/sys/class/net/wlan0/device/vendor")
        return "%s:%s" % (vendor_id, part_id)


    def check_approved_usb_part_id(self, cid):
        """
        Check if there are matching vendor_id:product_id pairs on the USB.
        """
        cmd = 'sudo /usr/sbin/lsusb -d %s'
        if not self._approved.has_key(cid):
            raise error.TestFail('%s missing from database' % cid)

        approved_devices = self._approved[cid]
        if '*' in approved_devices:
            self._system[cid] = [ '*' ]
            return

        for device in approved_devices:
            try:
                utils.system(cmd % device)
                self._system[cid] = [ device ]
                return
            except:
                pass
        self._failures[cid] = [ 'No match' ]


    def get_vendor_id_cardreader(self):
        dialog = site_ui.Dialog(question="Please insert a SD-card.",
                                choices=["OK"])
        if self._semiauto:
            num_retry = 3
        else:
            num_retry = 0

        part_id = ''
        while True:
            cmd = 'lsusb -v'
            output = utils.system_output(cmd)
            match = re.search(
                r'  idVendor +0x.... (.*?)\n(?:  .*\n)*?  .*?CARD READER',
                output, re.IGNORECASE)

            if match:
                part_id = match.group(1)
                break
            if not num_retry:
                part_id = 'N/A'
                break
            result = dialog.get_result()
            num_retry -= 1

        return part_id


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


    def run_once(self, approved_db=None, semiauto=False):
        self._semiauto = semiauto
        self._system = {}
        self._failures = {}

        if approved_db is None:
            approved_db = os.path.join(self.bindir, 'approved_components')

        if not os.path.exists(approved_db):
            raise error.TestError('Unable to find approved_db: %s' %
                                  approved_db)

        self._approved = eval(utils.read_file(approved_db))
        logging.debug('Approved DB: %s', self.pformat(self._approved))

        for cid in self._cids:
            self.check_component(cid, getattr(self, 'get_' + cid)())

        for cid in self._usb_cids:
            self.check_approved_usb_part_id(cid)

        logging.debug('System: %s', self.pformat(self._system))

        outdb = os.path.join(self.resultsdir, 'system_components')
        utils.open_write_close(outdb, self.pformat(self._system))

        if self._failures:
            raise error.TestFail(self.pformat(self._failures))
