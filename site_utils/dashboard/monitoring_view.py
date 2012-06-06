# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Class for tracking a few monitoring statistics.

This class allows time-based stats to be queried and updated into a local
db (json file) to track and notice unexpected trends in database data.
The initial example is to periodically record the count of the django_session
table over time and graph it to notice unexpected spikes.

Includes: class MonitoringView(object)
"""

import json
import os

MONITORING_DB_FILE = "monitoring_db.json"


class MonitoringView(object):
  """View used to show monitoring information in summary views.

  Initially, this will be used to watch for specific undesirable activities
  in the database.  Perhaps this will get re-abstracted into something more
  substantial.
  """

  def __init__(self, dash_base_dir):
    """Retrieve the contents of the current monitoring db file.

    No locking protects this file.

    Monitoring File should be of the following format:
    {
      "django_session": [{"time": "Wed Jun  6 10:33:02 PDT 2012",
                          "sessions": 170},
                         {"time": "Wed Jun  6 13:14:47 PDT 2012",
                          "sessions": 52422}, ...]
    }
    """
    self._monitoring_path = os.path.join(dash_base_dir, MONITORING_DB_FILE)
    if not os.path.exists(self._monitoring_path):
      self.monitoring_db = {'django_session': []}
    else:
      self.monitoring_db = json.load(open(self._monitoring_path))

  def UpdateMonitoringDB(self, db_key, updated_value_dict):
    """Add a newly retrieved data value to the in-memory db."""
    self.monitoring_db[db_key].append(updated_value_dict)

  def WriteMonitoringDB(self):
    """Write the updated monitoring db file.

    Not protected by locking code.
    """
    with open(self._monitoring_path, 'w') as f:
        f.write(json.dumps(self.monitoring_db))
