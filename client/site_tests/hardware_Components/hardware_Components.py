# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class hardware_Components(test.test):
    version = 1
    _syslog = '/var/log/messages'
    _cids = [
        'part_id_audio_codec',
        'part_id_chipset',
        'part_id_cpu',
        'part_id_ethernet',
        'part_id_storage',
        'part_id_usb_hosts',
        'part_id_vga',
        'part_id_wireless',
        'vendor_id_bluetooth',
        'vendor_id_touchpad',
        'vendor_id_webcam',
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


    def get_part_id_chipset(self):
        cmd = ('lspci | grep -E "^00:00.0 " | head -n 1 '
               '| sed s/.\*Host\ bridge://')
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_cpu(self):
        cmd = 'grep -m 1 \'model name\' /proc/cpuinfo | sed s/.\*://'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_ethernet(self):
        cmd = ('lspci | grep "Ethernet controller:" | head -n 1 '
               '| sed s/.\*Ethernet\ controller://')
        part_id = utils.system_output(cmd).strip()
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
        cmd = ('lspci | grep "Network controller:" | head -n 1 '
               '| sed s/.\*Network\ controller://')
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_vendor_id_bluetooth(self):
        cmd = ('hciconfig hci0 version | grep Manufacturer '
               '| sed s/.\*Manufacturer://')
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_vendor_id_touchpad(self):
        cmd = 'grep -i Touchpad /proc/bus/input/devices | sed s/.\*=//'
        part_id = utils.system_output(cmd).strip('"')
        return part_id


    def get_vendor_id_webcam(self):
        cmd = 'cat /sys/class/video4linux/video0/name'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def run_once(self, approved_db=None):
        self._system = {}
        self._failures = {}
        if approved_db is None:
            approved_db = os.path.join(self.bindir, 'approved_components')

        if not os.path.exists(approved_db):
            raise error.TestError('Unable to find approved_db: %s' %
                                  approved_db)

        self._approved = eval(utils.read_file(approved_db))
        logging.debug('Approved DB: %s', self._approved)

        for cid in self._cids:
            self.check_component(cid, getattr(self, 'get_' + cid)())

        logging.debug('System: %s', self._system)

        outdb = os.path.join(self.resultsdir, 'system_components')
        utils.open_write_close(outdb, str(self._system))

        if self._failures:
            raise error.TestFail(self._failures)
