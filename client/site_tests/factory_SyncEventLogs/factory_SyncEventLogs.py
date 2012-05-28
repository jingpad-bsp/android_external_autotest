# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Synchronously uploads event logs using EventLogWatcher.

import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.cros.factory.event_log_watcher import EventLogWatcher
from autotest_lib.client.cros.factory import shopfloor

class factory_SyncEventLogs(test.test):
    version = 1

    def run_once(self, require_shop_floor=None):
        if not require_shop_floor and not shopfloor.get_server_url():
            return

        self.shopfloor_client = shopfloor.get_instance()
        watcher = EventLogWatcher(
            handle_event_logs_callback=self._handle_event_logs)
        try:
            watcher.FlushEventLogs()
            watcher.Close()
        except:
            # Uh-oh, something went wrong.  Try our best to close the
            # watcher to preserve any existing state.
            try:
                watcher.Close()
            except:
                logging.exception('Unable to close EventLogWatcher')
            raise

    def _handle_event_logs(self, log_name, chunk):
        self.shopfloor_client.UploadEvent(log_name,
                                          shopfloor.Binary(chunk))
