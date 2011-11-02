# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for using Recall in autotest tests.

Recall is a server-side system that intercepts DNS, HTTP and HTTPS
traffic from clients for either recording or playback. This allows
tests to be run in labs without Internet access by playing back
pre-recorded copies of websites, allows tests to be run that use
recorded copies of sites known to exhibit errors or many iterations
of the same test to be run with the same data.

Recall is intended to be completely transparent to the client tests,
this base class takes case of adjusting the client's configuration to
redirect the traffic to the recall server (in the case it's not the
network's default gateway already) and install a root certificate
for HTTPS man-in-the-middling.

The base class is activated by arguments passed from the recall server
tests when invoking the client tests, and its implementation is
limited to the initialize() and cleanup() functions.
"""

import logging

from autotest_lib.client.bin import test


class RecallClientTest(test.test):
    """Base autotest class for client tests that can use Recall.

    Inherit this class for tests that should be optionally able to be
    run from a server test using Recall.

    If your subclass overrides the initialize() or cleanup() methods, it
    should make sure to invoke this class' version of those methods as well,
    and accept any unknown keyword arguments passing them to this class'
    version. The standard super(...) function cannot be used for this,
    since the base test class is not a 'new style' Python class.
    """
    def initialize(self, **dargs):
        """Initalize.

        Unknown arguments are passed to the super class' initialize function.
        """
        test.test.initialize(self, **dargs)

    def cleanup(self):
        """Clean up after running the test."""
        test.test.cleanup(self)
