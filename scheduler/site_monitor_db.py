# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#pylint: disable-msg=C0111

import os
import logging
import time

from autotest_lib.client.common_lib import global_config
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import email_manager
from autotest_lib.scheduler import scheduler_config, scheduler_models


# Override default parser with our site parser.
def parser_path(install_dir):
    """Return site implementation of parser.

    @param install_dir: installation directory.
    """
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


    def _check_queue_entry_statuses(self, queue_entries, allowed_hqe_statuses,
                                    allowed_host_statuses=None):
        """
        Forked from monitor_db.py
        """
        class_name = self.__class__.__name__
        for entry in queue_entries:
            if entry.status not in allowed_hqe_statuses:
                # In the orignal code, here we raise an exception. In an
                # effort to prevent downtime we will instead abort the job and
                # send out an email notifying us this has occured.
                error_message = ('%s attempting to start entry with invalid '
                                 'status %s: %s. Aborting Job: %s.'
                                 % (class_name, entry.status, entry,
                                    entry.job))
                logging.error(error_message)
                email_manager.manager.enqueue_notify_email(
                    'Job Aborted - Invalid Host Queue Entry Status',
                    error_message)
                entry.job.request_abort()
            invalid_host_status = (
                    allowed_host_statuses is not None
                    and entry.host.status not in allowed_host_statuses)
            if invalid_host_status:
                # In the orignal code, here we raise an exception. In an
                # effort to prevent downtime we will instead abort the job and
                # send out an email notifying us this has occured.
                error_message = ('%s attempting to start on queue entry with '
                                 'invalid host status %s: %s. Aborting Job: %s'
                                 % (class_name, entry.host.status, entry,
                                    entry.job))
                logging.error(error_message)
                email_manager.manager.enqueue_notify_email(
                    'Job Aborted - Invalid Host Status', error_message)
                entry.job.request_abort()
