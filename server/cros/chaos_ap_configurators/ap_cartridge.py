# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Queue
from threading import Thread

# Maximum configurators to run at once
THREAD_MAX = 15

class APCartridge(object):
    """Class to run multiple configurators in parallel."""


    def __init__(self):
        self.cartridge = Queue.Queue()


    def push_configurators(self, configurators):
        for configurator in configurators:
            self.cartridge.put(configurator)


    def push_configurator(self, configurator):
        self.cartridge.put(configurator)


    def _apply_settings(self):
        while True:
            configurator = self.cartridge.get()
            configurator.apply_settings()
            self.cartridge.task_done()


    def run_configurators(self):
        for i in range(THREAD_MAX):
            t = Thread(target=self._apply_settings)
            t.daemon = True
            t.start()
        self.cartridge.join()
