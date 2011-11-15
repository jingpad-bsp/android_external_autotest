# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recall server infrastructure.

Recall is a server-side system that intercepts DNS, HTTP and HTTPS
traffic from clients for recording, manipulation and playback. This
allows tests to be run in labs without Internet access by playing back
pre-recorded copies of websites, allows tests to be run that use
recorded copies of sites known to exhibit errors or many iterations
of the same test to be run with the same data.

The server infrastructure consists of DNS, HTTP and HTTPS servers and
a Certificate Authority that is used by the HTTPS server to generate
certificates on the fly as needed.

It also consists of DNS and HTTP clients, which are built in the
middleware pattern. Each server has an associated client that it will
use to fetch the necessary response. Clients can be stacked to build
functionality, for example:

    from autotest_lib.server.cros import recall
    c = recall.ArchivingHTTPClient(
          recall.DeterministicScriptInjector(
              recall.HTTPClient()))

This would create a client that after fetching the response from the
Internet modifies it to inject JavaScript code to wrap Math.random()
and Date() before finally archiving it. The order is important, since
this means the archived response is already pre-mutated.

To run an autotest client test on a remote machine wrapped in a
Recall server instance for the most common use cases you only need use
the pre-written test_RecallServer test.

If you need to create a custom type of autotest server test, you can
subclass that test from RecallServerTest to deal with the heavy lifting
of reconfiguring the server to redirect traffic from the client.

Finally, the classes in this module on their own are useful for building
a standalone Recall server on a preconfigured system, perhaps with a DHCP
server that already directs clients to it.
"""

# The code is split amongst multiple files for maintainability, this is
# not intended to be exposed to other Python code, instead they should
# treat it as a single module.
#
# This is correct:
#   from autotest_lib.server.cros import recall
# so is this:
#   import autotest_lib.server.cros.recall
#
# But this is NOT:
#   from autotest_lib.server.cros.recall import dns_server
#
# We use __all__ in each of the files so that the following only imports
# the public API. This is a minor sprain of the coding style, but one that
# aids usability of this package.
from certificate_authority import *
from dns_client import *
from dns_server import *
from http_client import *
from http_server import *
from middleware import *
