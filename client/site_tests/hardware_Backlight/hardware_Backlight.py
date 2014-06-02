# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import power_utils, service_stopper


class hardware_Backlight(test.test):
    version = 1

    def initialize(self):
        """Perform necessary initialization prior to test run.

        Private Attributes:
          _backlight: power_utils.Backlight object
          _services: service_stopper.ServiceStopper object
        """
        super(hardware_Backlight, self).initialize()
        self._backlight = None
        # Stop powerd to avoid it adjusting backlight levels
        self._services = service_stopper.ServiceStopper(['powerd'])
        self._services.stop_services()


    def run_once(self):
        # optionally test keyboard backlight
        kblight = None
        kblight_errs = 0
        try:
            kblight = power_utils.KbdBacklight()
        except power_utils.KbdBacklightException as e:
            logging.info("Assuming no keyboard backlight due to %s", str(e))

        if kblight:
            init_percent = kblight.get()
            try:
                for i in xrange(100, -1, -1):
                    kblight.set(i)
                    result = int(kblight.get())
                    if i != result:
                        logging.error('keyboard backlight set %d != %d get',
                                      i, result)
                        kblight_errs += 1
            finally:
                kblight.set(init_percent)

        if kblight_errs:
            raise error.TestFail("%d errors testing keyboard backlight." % \
                                 kblight_errs)

        self._backlight = power_utils.Backlight()
        backlight_errs = 0
        for i in xrange(self._backlight.get_max_level() + 1):
            self._backlight.set_level(i)
            result = self._backlight.get_level()
            if i != result:
                backlight_errs += 1
                logging.error('backlight set %d != %d get', i, result)

        if backlight_errs:
            raise error.TestFail("%d errors testing backlight." % \
                                 backlight_errs)


    def cleanup(self):
        if self._backlight:
            self._backlight.restore()
        self._services.restore_services()
        super(hardware_Backlight, self).cleanup()
