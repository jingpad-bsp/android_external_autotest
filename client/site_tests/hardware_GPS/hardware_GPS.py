# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils


class hardware_GPS(test.test):
    version = 1

    def run_once(self):
        match = False
        gpspipe = utils.system_output('gpspipe -r -n 10', timeout=60)
        logging.debug(gpspipe)
        for line in gpspipe.split('\n'):
            line = line.strip()
            
            match = re.search(
                r'^\$GPRMC\,(.*)\,(.*)\,(.*)\,(.*)\,(.*)\,(.*)\,(.*)\,(.*)\,' +
                r'(.*)\,(.*)\,(.*)\*(.*)$',
                line)
                
            if match:
                logging.debug('Time = %s', match.group(1))
                logging.debug('Status = %s', match.group(2))
                logging.debug('Latitude = %s %s', match.group(3),
                              match.group(4))
                logging.debug('Longitude = %s %s', match.group(5),
                              match.group(6))
                logging.debug('Speed = %s', match.group(7))
                logging.debug('Track Angle = %s', match.group(8))
                logging.debug('Date = %s', match.group(9))
                logging.debug('Magnetic Variation = %s %s', match.group(10),
                              match.group(11))
                break
                
        if not match:
            raise error.TestFail('Unable to find GPS devices')

