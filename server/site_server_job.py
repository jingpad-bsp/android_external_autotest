# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import common
import utils


def get_site_job_data(job):
    """Add custom data to the job keyval info.

    When multiple machines are used in a job, change the hostname to
    the platform of the first machine instead of machine1,machine2,...  This
    makes the job reports easier to read and keeps the tko_machines table from
    growing too large.

    Args:
        job: instance of server_job.

    Returns:
        keyval dictionary with new hostname value, or empty dictionary.
    """
    site_job_data = {}
    # Only modify hostname on multimachine jobs. Assume all host have the same
    # platform.
    if len(job.machines) > 1:
        # Search through machines for first machine with a platform.
        for host in job.machines:
            keyval_path = os.path.join(job.resultdir, 'host_keyvals', host)
            keyvals = utils.read_keyval(keyval_path)
            host_plat = keyvals.get('platform', None)
            if not host_plat:
                continue
            site_job_data['hostname'] = host_plat
            break
    return site_job_data


class site_server_job(object):
    pass
