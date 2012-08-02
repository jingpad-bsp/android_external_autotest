# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from autotest_lib.client.common_lib import global_config
from autotest_lib.scheduler import scheduler_config

HOSTS_JOB_SUBDIR = 'hosts/'


class SiteDroneManager(object):


    def copy_to_results_repository(self, process, source_path,
                                   destination_path=None):
        """
        Copy results from the given process at source_path to destination_path
        in the results repository.

        This site subclassed version will only copy the results back for Special
        Agent Tasks (Cleanup, Verify, Repair) that reside in the hosts/
        subdirectory of results if the copy_task_results_back flag has been set
        to True inside global_config.ini
        """
        copy_task_results_back = global_config.global_config.get_config_value(
                scheduler_config.CONFIG_SECTION, 'copy_task_results_back',
                type=bool)
        special_task = source_path.startswith(HOSTS_JOB_SUBDIR)
        if copy_task_results_back or not special_task:
            super(SiteDroneManager, self).copy_to_results_repository(process,
                    source_path, destination_path)