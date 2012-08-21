# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging

from autotest_lib.client.common_lib import global_config
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import scheduler_config, scheduler_models

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


class SiteDispatcher(object):
    """
    SiteDispatcher subclasses BaseDispatcher in monitor_db.
    """
    DEFAULT_REQUESTED_BY_USER_ID = 1


    def _reverify_hosts_where(self, where,
                              print_message='Reverifying host %s'):
        """
        This is an altered version of _reverify_hosts_where the class to
        models.SpecialTask.objects.create passes in an argument for
        requested_by, in order to allow the Cleanup task to be created
        properly.
        """
        full_where='locked = 0 AND invalid = 0 AND ' + where
        for host in scheduler_models.Host.fetch(where=full_where):
            if self.host_has_agent(host):
                # host has already been recovered in some way
                continue
            if self._host_has_scheduled_special_task(host):
                # host will have a special task scheduled on the next cycle
                continue
            if print_message:
                logging.error(print_message, host.hostname)
            try:
                user = models.User.objects.get(login='autotest_system')
            except models.User.DoesNotExist:
                user = models.User.objects.get(
                        id=SiteDispatcher.DEFAULT_REQUESTED_BY_USER_ID)
            models.SpecialTask.objects.create(
                    task=models.SpecialTask.Task.CLEANUP,
                    host=models.Host.objects.get(id=host.id),
                    requested_by=user)