# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_ui, utils


_QUESTION_START = '''
<h5>
The Bluetooth scan discovered the following devices.<br>
If a device is not on the list, switch it into pairing mode and rescan.<br>
</h5>
<table border="1"><tr><td>Address</td><td>Name</td></tr>
'''


class desktopui_BluetoothSemiAuto(test.test):
    version = 1

    def run_once(self, timeout=60):
        while True:
            question = _QUESTION_START
            hciscan = utils.system_output('hcitool scan')
            logging.debug(hciscan)
            for line in hciscan.split('\n'):
                line = line.strip()
                match = re.search(r'^(..:..:..:..:..:..)\s+(.*)$', line)
                if match:
                    question += '<tr>'
                    question += '<td>' + match.group(1) + '</td>'
                    question += '<td>' + match.group(2) + '</td>'
                    question += '</tr>'
            question += '</table><br>'

            dialog = site_ui.Dialog(question=question,
                                    choices=['Pass', 'Fail', 'Rescan'])
            result = dialog.get_result()
            if result is None:
                raise error.TestFail('Timeout')
            if result == 'Pass':
                return
            if result == 'Fail':
                raise error.TestFail('Unable to find Bluetooth devices')
