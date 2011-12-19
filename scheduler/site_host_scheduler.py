# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Chrome OS Autotest scheduling utility.

We do not import host_scheduler directly here and rely upon the MixIn
implementation in site_import_class / BaseClass to do this for us.  This is
to avoid the loop in the dependency graph of depending on host_scheduler as
host_scheduler directly imports its site_ implementation.
"""

LABEL_DELIMTER = '+'


class site_host_scheduler():
    """Handles the logic for choosing when to run jobs and on which hosts.

    This class overrides the necessary methods to treat labels as possibly
    complex labels of dependencies separated with a custom delimiter. This class
    parses the complex label into simpler labels and performs the operation on
    the hosts that match the union of these labels.
    """

    def hosts_in_label(self, label_id):
        label_ids = label_id.split(LABEL_DELIMTER)
        # Bootstrap set with hosts from first label in list.
        hosts_for_label_set = set(self._label_hosts.get(label_ids[0], ()))
        for label_id in label_ids[1:]:
            hosts_for_label_set.intersection_update(set(
                    self._label_hosts.get(label_id, ())))

        return hosts_for_label_set


    def remove_host_from_label(self, host_id, label_id):
      label_ids = label_id.split(LABEL_DELIMTER)
      for label in label_ids:
        self._label_hosts[label].remove(host_id)
