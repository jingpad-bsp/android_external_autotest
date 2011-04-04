# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

def get_site_job_data(job):
    """Add custom data to the job keyval info.

    When multiple machines are used in a job, change the hostname to
    SERVER_JOB instead of machine1,machine2,...  This makes the job reports
    easier to read and keeps the tko_machines table from growing too large.
    """
    site_job_data = {}
    if len(job.machines) > 1:
        site_job_data['hostname'] = 'SERVER_JOB'
    return site_job_data

class site_server_job():
    pass