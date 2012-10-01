# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import threading


class ControlledStressor(threading.Thread):
    def __init__(self, stressor):
        """Run a stressor callable in a threaded loop on demand.

        Creates a new thread and runs |stressor| in a loop until told to stop.

        Args:
          stressor: callable which performs a single stress event
        """
        super(ControlledStressor, self).__init__()
        self.daemon = True
        self._complete = threading.Event()
        self._stressor = stressor


    def run(self):
        """Overloaded from threading.Thread."""
        while not self._complete.is_set():
            self._stressor()


    def start(self):
        """Start applying the stressor."""
        self._complete.clear()
        super(ControlledStressor, self).start()


    def stop(self, timeout=45):
        """Stop applying the stressor.

        Args:
          timeout: maximum time to wait for a single run of the stressor to
              complete, defaults to 45 seconds."""
        self._complete.set()
        self.join(timeout)


class CountedStressor(threading.Thread):
    def __init__(self, stressor):
        """Run a stressor callable in a threaded loop a given number of times.

        Args:
          stressor: callable which performs a single stress event
        """
        super(CountedStressor, self).__init__()
        self.daemon = True
        self._stressor = stressor


    def run(self):
        """Overloaded from threading.Thread."""
        for i in xrange(self._count):
            self._stressor()


    def start(self, count):
        """Apply the stressor a given number of times.

        Args:
          count: number of times to apply the stressor
        """
        self._count = count
        super(CountedStressor, self).start()


    def wait(self, timeout=None):
        """Wait until the stressor completes.

        Args:
          timeout: maximum time for the thread to complete, by default never
              times out.
        """
        self.join(timeout)
