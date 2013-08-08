# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import collections
import logging
import os

import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.server.cros.dynamic_suite import reimager
from autotest_lib.site_utils import suite_preprocessor


default_num = global_config.global_config.get_config_value(
    "CROS", "sharding_factor", default=1, type=int)


def NumOfTask(task):
  """
  Take a run and produce the number of machines it will run across.

  This seems easy, because |task.num| exists. However, it is |None| for any
  suite that doesn't specify |num|. This is needed so that we know when to pass
  in a num, and when not to because the server can override the default
  sharding factor locally. Therefore, we need to compensate for this when doing
  our local analysis here and provide the default sharding factor if we see
  |num| is None.

  @param task The task to get the |num| for.
  @return |num| for this task.
  """
  if task.num is None:
    return default_num
  else:
    return int(task.num)


# TODO(milleral): crosbug.com/37623
# DEPENDENCIES-related code needs to be refactored a bit so that trying to
# gather all the dependencies and analyze them doesn't require reaching into
# random pieces of code across the codebase nor reaching into other object's
# private methods.

def CheckDependencies(tasks):
    """
    Iterate through all of the tasks that suite_scheduler will process, and warn
    if any of the tasks are set to run a suite with a |num| such that the suite
    will not be able to satisfy all of its HostSpecs. This can happen when a
    new test is added to a suite that increases the overall number of
    HostSpecs, and |num| was not bumped up accordingly.

    If the default sharding_factor is ever changed in the shadow_config on the
    server, this sanity check will no longer give correct results.

    @param tasks The list of tasks to check.
    @return 0 if no problems are found
            1 if problems are found
    """
    test_deps = suite_preprocessor.calculate_dependencies(common.autotest_dir)

    by_suite = collections.defaultdict(list)
    for task in tasks:
        by_suite.setdefault(task.suite, []).append(task)

    corrections = []
    for suitename, control_deps in test_deps.items():
        if not suitename:
            continue
        imager = reimager.OsReimager(common.autotest_dir, 'none')

        # Figure out what kind of hosts we need to grab.
        per_test_specs = imager._build_host_specs_from_dependencies(
                None, None, control_deps).values()

        hostspecs = len(set([x for x in per_test_specs]))

        for task in by_suite[suitename]:
            if hostspecs > NumOfTask(task):
                corrections.append((task.name, hostspecs))

    for c in corrections:
        # Failures to parse a config entry result in a logging.warn(),
        # so let's keep the output the same across different errors
        logging.warn("Increase %s to |num: %d|", c[0], c[1])

    return 1 if corrections else 0


def CheckControlFileExistance(tasks):
    """
    Make sure that for any task that schedules a suite, that
    test_suites/control.<suite> exists. this prevents people from accidentally
    adding a suite to suite_scheduler.ini but not adding an actual suite
    control file, thus resulting in their suite not running and the lab team
    getting lots of email

    @param tasks The list of tasks to check.
    @return 0 if no missing control files are found
            1 if there are at least one missing control files
    """
    corrections = False

    for task in tasks:
        suite_path = os.path.join(common.autotest_dir,
                                  'test_suites', 'control.'+task.suite)
        if not os.path.exists(suite_path):
            corrections = True
            logging.warn("No suite control file for %s", task.suite)

    return 1 if corrections else 0
