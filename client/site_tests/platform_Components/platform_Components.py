# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class platform_Components(test.test):
    version = 1
    _syslog = '/var/log/messages'
    _audio =  '/proc/asound/*'
    result = ""


    def check_component(self, comp_key, comp_id):
        self._system[comp_key] = [ comp_id ]

        if not self._approved.has_key(comp_key):
            raise error.TestFail('%s missing from database' % comp_key)

        app_ids = self._approved[comp_key]
        if '*' in app_ids:
            return

        flag = 0
        for name in app_ids:
            if re.search(name, comp_id)==None:
                flag += 1

        if flag == len(app_ids):
                self.result += comp_key + ': Not Approved '
        else:
                self.result += comp_key + ': Approved '

    # More get methods go here...
    def get_part_id_audio_codec(self):
        cmd = 'grep -R Codec: %s | head -n 1 | sed s/.\*Codec://' % self._audio
        part_id = utils.system_output(cmd).strip()
        return part_id

    def get_part_id_bluetooth(self):
        cmd = 'grep -m 1 Bluetooth: %s | sed s/.\*Bluetooth://' % self._syslog
        part_id = utils.system_output(cmd).strip()
        return part_id

    def get_part_id_cpu(self):
        cmd = 'grep -i -m 1 CPU0: %s | sed s/.\*CPU0://' % self._syslog
        part_id = utils.system_output(cmd).strip()
        return part_id

    def get_part_id_chipset(self):
        cmd = 'grep -i -m 1 Chipset %s | sed s/.\*kernel://' % self._syslog
        part_id = utils.system_output(cmd).strip()
        return part_id

    def get_part_id_touchpad(self):
        cmd = 'grep -i -m 1 touchpad %s | sed s/.\*kernel://' % self._syslog
        part_id = utils.system_output(cmd).strip()
        return part_id

    def get_part_id_webcam(self):
        cmd = 'grep -i -m 1 camera %s | sed s/.\*kernel://' % self._syslog
        part_id = utils.system_output(cmd).strip()
        return part_id


    def run_once(self, approved_db=None):
        self._system = {}
        if approved_db is None:
            approved_db = 'approved_components'
        db = os.path.join(self.bindir, approved_db)
        self._approved = eval(utils.read_file(db))

        self.check_component('part_id_audio_codec', 
                             self.get_part_id_audio_codec())
        self.check_component('part_id_bluetooth', self.get_part_id_bluetooth())
        self.check_component('part_id_cpu', self.get_part_id_cpu())
        self.check_component('part_id_chipset', self.get_part_id_chipset())
        self.check_component('part_id_touchpad', self.get_part_id_touchpad())
        self.check_component('part_id_webcam', self.get_part_id_webcam())

        # More get/check calls go here...

        logging.debug(self._system)
        logging.debug(self._approved)

        outdb = os.path.join(self.resultsdir, 'system_components')
        utils.open_write_close(outdb, str(self._system))
     
        if self.result != "":
            raise error.TestFail(self.result)

