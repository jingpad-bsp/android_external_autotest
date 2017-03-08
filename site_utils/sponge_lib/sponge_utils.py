# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains utilities for test to report result to Sponge.
"""

import logging
import traceback

from autotest_lib.site_utils.sponge_lib import autotest_dynamic_job
from autotest_lib.client.common_lib import decorators

try:
    import sponge
except ImportError:
    logging.debug('Module failed to be imported: sponge')
    sponge = None


@decorators.test_module_available(sponge)
def upload_results(job, log=logging.debug):
    """Upload test results to Sponge with given job details.

    @param job: A job object created by tko/parsers.
    @param log: Logging method, default is logging.debug.

    @return: A url to the Sponge invocation.
    """
    try:
        info = autotest_dynamic_job.DynamicJobInfo(job)
        return sponge.upload_utils.UploadInfo(info)
    except:
        stack = traceback.format_exc()
        log('Failed to upload to sponge.')
        log(str(stack))

