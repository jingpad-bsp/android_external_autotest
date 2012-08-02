# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.common_lib import global_config
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import scheduler_config

# Override default parser with our site parser.
def parser_path(install_dir):
    return os.path.join(install_dir, 'tko', 'site_parse')


class SiteAgentTask(object):
    """
    SiteAgentTask subclasses BaseAgentTask in monitor_db.
    """


    def _archive_results(self, queue_entries):
        """
        Set the status of queue_entries to ARCHIVING.

        This method sets the status of the queue_entries to ARCHIVING
        if the enable_archiving flag is true in global_config.ini.
        Otherwise, it bypasses the archiving step and sets the queue entries
        to the final status of current step.
        """
        enable_archiving = global_config.global_config.get_config_value(
            scheduler_config.CONFIG_SECTION, 'enable_archiving', type=bool)
        # Set the status of the queue entries to archiving or self final status
        if enable_archiving:
            status = models.HostQueueEntry.Status.ARCHIVING
        else:
            status = self._final_status()

        for queue_entry in self.queue_entries:
            queue_entry.set_status(status)
