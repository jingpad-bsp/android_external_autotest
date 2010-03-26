# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, time
from autotest_lib.client.bin import site_ui_test
from autotest_lib.client.common_lib import error

class desktopui_ChromeFirstRender(site_ui_test.UITest):
    version = 1


    def __parse_uptime(self, target_file):
        data = file(target_file).read()
        time = re.split(r' +', data.strip())[0]
        return float(time)
        

    def run_once(self):
        try:            
            time.sleep(10) # Wait for chrome to render.
            start_time = self.__parse_uptime('/tmp/uptime-login-successful')
            end_time = self.__parse_uptime('/tmp/uptime-chrome-first-render')
            self.write_perf_keyval({'seconds_chrome_first_tab':
                                      end_time - start_time})            
        except IOError, e:
            logging.debug(e)
            raise error.TestFail('Login information missing')

