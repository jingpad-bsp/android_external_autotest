# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import Queue
import traceback
from threading import Thread

# Maximum configurators to run at once
THREAD_MAX = 15

class APCartridge(object):
    """Class to run multiple configurators in parallel."""


    def __init__(self):
        self.cartridge = Queue.Queue()


    def push_configurators(self, configurators):
        """Adds multiple configurators to the cartridge.

        @param configurators: a list of configurator objects.
        """
        for configurator in configurators:
            self.cartridge.put(configurator)


    def push_configurator(self, configurator):
        """Adds a configurator to the cartridge.

        @param configurator: a configurator object.
        """
        self.cartridge.put(configurator)


    def _apply_settings(self):
        while True:
            configurator = self.cartridge.get()
            try:
                configurator.apply_settings()
            except Exception:
                trace = ''.join(traceback.format_exc())
                configurator.store_config_failure(trace)
                logging.error('Configuration failed for AP: %s\n%s',
                              configurator.get_router_name(), trace)
                configurator.reset_command_list()
            logging.info('Configuration of AP %s complete.',
                         configurator.get_router_name())
            self.cartridge.task_done()


    def run_configurators(self):
        """Runs apply_settings for all configurators in the cartridge."""
        for i in range(THREAD_MAX):
            t = Thread(target=self._apply_settings)
            t.daemon = True
            t.start()
        self.cartridge.join()
