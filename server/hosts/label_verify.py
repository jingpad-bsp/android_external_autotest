# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module defines the Label Verifier class."""


import common
from autotest_lib.client.common_lib import hosts


class LabelVerifier(hosts.Verifier):
    """
    Verifier to ensure a host's labels are up-to-date.

    This verifier runs the host's update_label method to clear out old labels
    that are not valid anymore and adds new labels that aren't already there.
    """

    def verify(self, host):
        host.labels.update_labels(host)


    @property
    def description(self):
        return 'Ensure the host labels are up-to-date'
