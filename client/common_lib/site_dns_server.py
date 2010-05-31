# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, threading, time, utils

class LocalDns(object):
    """a wrapper around miniFakeDns that handles managing running the server
    in a separate thread.
    """

    def __init__(self, fake_ip="127.0.0.1", local_port=53):
        import miniFakeDns  # So we don't need to install it in the chroot.
        self._dns = miniFakeDns.DNSServer(fake_ip="127.0.0.1", port=local_port)
        self._stopper = threading.Event()
        self._thread = threading.Thread(target=self._dns.run,
                                        args=(self._stopper,))


    def run(self):
        self._thread.start()


    def stop(self):
        self._stopper.set()
        self._thread.join()
