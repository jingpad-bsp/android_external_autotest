# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mox
import threading
import time

from autotest_lib.client.common_lib import decorators


class InContextTest(mox.MoxTestBase):
    """ Unit tests for the in_context decorator. """

    @decorators.in_context('lock')
    def inc_count(self):
        """ Do a slow, racy read/write. """
        temp = self.count
        time.sleep(0.0001)
        self.count = temp + 1


    def testDecorator(self):
        """ Test that the decorator works by using it with a lock. """
        self.count = 0
        self.lock = threading.RLock()
        iters = 100
        num_threads = 20
        # Note that it is important for us to go through all this bother to call
        # a method in_context N times rather than call a method in_context that
        # does something N times, because by doing the former, we acquire the
        # context N times (1 time for the latter).
        thread_body = lambda f, n: [f() for i in xrange(n)]
        threads = [threading.Thread(target=thread_body,
                                    args=(self.inc_count, iters))
                   for i in xrange(num_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEquals(iters * num_threads, self.count)
