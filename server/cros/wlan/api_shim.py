# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

import common

from autotest_lib.server import autotest

class ApiShim(object):
    """Wraps site_wlan scripts so they can be used as though they were a library

    The tools in site_wlan were written to be used as command-line tools.
    In order to avoid increasing the number of tests that rely on running
    these as standalone tools, wrap them in an API to create an abstraction.
    Then we can refactor the tools into a library that implements that API,
    and some command-line wrappers for standalone usage.
    """


    def __init__(self, host):
        """Constructor

        @param host: a hosts.Host object pointed at the DUT.
        """
        self._script = self._build_script_path(host)
        self._client = host


    @classmethod
    def _script_name(cls):
        """Returns the name of the script this class wraps."""
        raise NotImplementedError()


    def _build_script_path(self, host):
        """Returns fully-specified path to wrapped script.

        @param host: a hosts.Host object pointed at the DUT.

        @return fully-specified path to the wrapped script.
        """
        # There's de-facto only one autodir path on clients.
        autodir = autotest.Autotest.get_client_autodir_paths(host)[0]
        return os.path.join(autodir, 'common_lib', 'cros', 'site_wlan',
                            self._script_name())
