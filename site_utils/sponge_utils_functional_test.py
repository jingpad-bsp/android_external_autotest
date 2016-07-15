# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Test methods in module sponge_utils.

This test has dependency on sponge module, therefore it's not a unit test.
User can run this module manually to verify test results can be compiled into
Sponge XML and uploaded to test server correctly.
"""

import mox
import os
import tempfile
import time
import unittest

import common
from autotest_lib.site_utils import sponge_utils
from autotest_lib.tko import models


ACTS_SUMMARY_JSON = """
{
    "Results": [
        {
            "Begin Time": 1464054883744,
            "Details": "setup_class failed for FilteringTest.",
            "End Time": 1464054883744,
            "Extras": null,
            "Result": "FAIL",
            "Test Class": "FilteringTest",
            "Test Name": "",
            "UID": null,
            "Extra Errors": {"on_fail": "I also failed for whatever reason"}
        },
        {
            "Begin Time": 1464054888355,
            "Details": null,
            "End Time": 1464054888644,
            "Extras": null,
            "Result": "PASS",
            "Test Class": "UniqueFilteringTest",
            "Test Name": "test_scan_flush_pending_scan_results",
            "UID": null,
            "Extra Errors": {}
        }
    ],
    "Summary": {
        "Executed": 2,
        "Failed": 1,
        "Passed": 1,
        "Requested": 10,
        "Skipped": 0,
        "Unknown": 8
    }
}
"""

class SpongeUtilsUnitTests(mox.MoxTestBase):
    """Test functions in sponge_utils.
    """

    def setUp(self):
        """Set up test."""
        super(SpongeUtilsUnitTests, self).setUp()
        self.acts_summary = tempfile.NamedTemporaryFile(delete=False)
        self.acts_summary.write(ACTS_SUMMARY_JSON)
        self.acts_summary.close()

    def tearDown(self):
        """Delete temporary file.
        """
        super(SpongeUtilsUnitTests, self).tearDown()
        os.unlink(self.acts_summary.name)

    def test_upload_results_in_test(self):
        """Test function upload_results_in_test.
        """
        test = self.mox.CreateMockAnything()
        test.resultsdir = ('/usr/local/autotest/results/123-debug_user/host1/'
                           'dummy_PassServer')
        test.tagged_testname = 'dummy_PassServer'

        test.job = self.mox.CreateMockAnything()
        test.job.user = 'debug_user'
        test.job.machines = ['host1']

        job_keyvals = {'drone': 'localhost',
                       'job_started': time.time()-1000}
        self.mox.StubOutWithMock(models.test, 'parse_job_keyval')
        models.test.parse_job_keyval(test.resultsdir).AndReturn(job_keyvals)

        self.mox.ReplayAll()

        invocation_url = sponge_utils.upload_results_in_test(
                test, test_pass=True, acts_summary=self.acts_summary.name)
        print 'Invocation URL: %s' % invocation_url
        self.assertIsNotNone(invocation_url)


if __name__ == '__main__':
    unittest.main()
