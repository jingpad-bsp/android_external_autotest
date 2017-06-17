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


class SiteAgentTask(object):
    """
    SiteAgentTask subclasses BaseAgentTask in monitor_db.
    """


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
