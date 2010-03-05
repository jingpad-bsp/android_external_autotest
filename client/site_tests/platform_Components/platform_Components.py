# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class platform_Components(test.test):
    version = 1
    _syslog = '/var/log/messages'


    def check_component(self, comp_key, comp_id):
        self._system[comp_key] = [ comp_id ]

        if not self._approved.has_key(comp_key):
            raise error.TestFail('%s missing from database' % comp_key)

        app_ids = self._approved[comp_key]
        if '*' in app_ids:
            return
        if not comp_id in app_ids:
            raise error.TestFail('%s="%s" is not approved' %
                                 (comp_key, comp_id))


    def get_part_id_cpu(self):
        cmd = 'grep -i -m 1 CPU0: %s | sed s/.\*CPU0://' % self._syslog
        part_id = utils.system_output(cmd).strip()
        return part_id


    # More get methods go here...


    def run_once(self, approved_db=None):
        self._system = {}
        if approved_db is None:
            approved_db = 'approved_components'
        db = os.path.join(self.bindir, approved_db)
        self._approved = eval(utils.read_file(db))

        self.check_component('part_id_cpu', self.get_part_id_cpu())

        # More get/check calls go here...

        logging.debug(self._system)
        logging.debug(self._approved)

        outdb = os.path.join(self.resultsdir, 'system_components')
        utils.open_write_close(outdb, str(self._system))
