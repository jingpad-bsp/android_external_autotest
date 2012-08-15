#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Clean Staged Images.

This script is responsible for removing older builds from the Chrome OS
devserver as well as old cros-version: labels from the Autotest DB.

There are two different options to remove builds, one is for "regular builds"
which is builds that happen around 4 times a day, and the other option is for
"Paladin builds" which are builds that happen as part of the Commit Queue and
are far more frequent. Since Paladin builds are only used for the BVT HWTest
Step we can be more agressive when it comes to pruning these builds.
"""

from distutils import version
import optparse
import glob
import logging
import os
import re
import sys
import shutil
import time

import common
from autotest_lib.server import frontend
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.cli.rpc import AFE_RPC_PATH
from autotest_lib.client.common_lib import global_config, logging_config
from autotest_lib.server.cros.dynamic_suite.constants import VERSION_PREFIX

# This filename must be kept in sync with devserver's downloader.py
_TIMESTAMP_FILENAME = 'staged.timestamp'
_HOURS_TO_SECONDS = 60*60


class CleanStagedImagesLoggingConfig(logging_config.LoggingConfig):
    def configure_logging(self, results_dir=None, verbose=False):
        super(CleanStagedImagesLoggingConfig, self).configure_logging(
                use_console=True, verbose=verbose)


def validate_and_parse_build_milestone(build_name):
    """Parse the build name and ensure it is a proper build name.

    Example build name: R21-4555.2.3 or R21-2368.0.0-rc30
    @param  build_name: The name of the build.
    @returns the milestone of the build if it is valid.
    """
    pattern = '(R\d+)-(\d+\.\d+\.\d+(-rc\d+|$))'
    match = re.match(pattern, build_name)
    if match:
        return match.group(1)


def sort_builds(build_list):
    """Sort a list of builds of format R21-121.0.0 or R21-121.0.0-rc3.

    @param build_list: The list of builds to sort.
    @returns a list of builds sorted in reverse order.
    """
    return sorted(build_list, key=lambda s: version.LooseVersion(s),
                  reverse=True)


def file_is_too_old(build_path, max_age_hours):
    """Test to see if the build at |build_path| is older than |max_age_hours|.

    @param build_path The path to the build (ie. 'build_dir/R21-2035.0.0')
    @param max_age_hours The maximum allowed age of a build in hours.
    @return True if the build is older than |max_age|, False otherwise.
    """
    cutoff = time.time() - max_age_hours * _HOURS_TO_SECONDS
    timestamp_path = os.path.join(build_path, _TIMESTAMP_FILENAME)
    if os.path.exists(timestamp_path):
        age = os.stat(timestamp_path).st_mtime
        if age < cutoff:
            return True
    else:
        # If the timestamp doesn't exist, then make one so we can wipe the
        # build on a later run.
        with open(timestamp_path, 'a'):
            os.utime(timestamp_path, None)
    return False


def prune_builds(build_dir, max_age_hours):
    """Remove any builds older than |max_age_hours| hours old.

    Prune a directory down to only having builds last used sooner than
    |max_age_hours| seconds ago. This will prune down all milestones to only
    having fresh builds.

    @param build_dir: The build dir to prune builds in.
    @param max_age_hours: The max age in hours of builds to keep around.
    """
    logging.debug('Pruning %s down to builds older than %d hours ago.',
                  build_dir, max_age_hours)
    build_dict = {}
    # Create a dict that is of the format:
    # build_dict[milestone][build_name] = build_path
    # e.g. {'R21' : {'R21-2056.0.0': 'build_dir/R21-2056.0.0',
    #                'R21-2035.0.0': 'build_dir/R21-2035.0.0'}
    for entry in glob.glob(build_dir + '/*'):
        build_name = os.path.basename(entry)
        milestone = validate_and_parse_build_milestone(build_name)
        if not milestone:
            logging.debug('Skipping %s', build_name)
            continue
        build_dict.setdefault(milestone, {})[os.path.basename(entry)] = entry

    for milestone in build_dict:
        for (entry, path) in build_dict[milestone].items():
            if file_is_too_old(path, max_age_hours):
                logging.debug('Deleting %s', path)
                shutil.rmtree(path)


def delete_labels_of_unstaged_builds(build_dir):
    """Delete labels of builds that are no longer staged on the dev server.

    @param build_dir: The build dir to compare known labels against.
    """
    autotest_server = global_config.global_config.get_config_value('SERVER',
                                                                   'hostname')
    web_server = 'http://%s/%s' % (autotest_server, AFE_RPC_PATH)
    rpc_interface = rpc_client_lib.get_proxy(web_server)
    builder_name = os.path.basename(build_dir.rstrip('/')).split('/')[-1]
    vers = '%s%s/' % (VERSION_PREFIX, builder_name)
    all_labels = rpc_interface.get_labels(name__startswith=vers)
    # Build a list of cros-version:build_name/CROS_VERSION.
    # e.g. cros-version:x86-mario-release/R20-2268.41.0
    build_labels_to_keep = [vers + os.path.basename(entry) for entry in
                    glob.glob(build_dir + '/*')]
    for label in all_labels:
        if label['name'] not in build_labels_to_keep:
            logging.debug('Removing label %s', label['name'])
            rpc_interface.delete_label(label['id'])


def prune_builds_and_labels(builds_dir, keep_duration, keep_paladin_duration):
    """Prune the build dirs and also delete old labels.

    @param builds_dir: The builds dir where all builds are staged.
      on the chromeos-devserver this is ~chromeos-test/images/
    @param keep_duration: How old of regular builds to keep around.
    @param keep_paladin_duration: How old of Paladin builds to keep around.
    """
    if not os.path.exists(builds_dir):
        logging.error('Builds dir %s does not exist', builds_dir)
        return

    for build_dir in glob.glob(builds_dir + '/*'):
        logging.debug('Processing %s', build_dir)
        if build_dir.endswith('-paladin'):
            keep = keep_paladin_duration
        else:
            keep = keep_duration

        prune_builds(build_dir, keep)
        # TODO(scottz): Skip label pruning for now.
        # Refer to bug crosbug.com/33247
        # delete_labels_of_unstaged_builds(build_dir)

def main():
    usage = 'usage: %prog [options] images_dir'
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-a', '--max-age', default=24, type=int,
                      help='Number of hours to keep normal builds: %default')
    parser.add_option('-p', '--max-paladin-age', default=24, type=int,
                      help='Number of hours to keep paladin builds: %default')
    parser.add_option('-v', '--verbose',
                      dest='verbose', action='store_true', default=False,
                      help='Run in verbose mode')
    options, args = parser.parse_args()
    if len(args) != 1:
      parser.print_usage()
      sys.exit(1)

    if options.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    prune_builds_and_labels(args[0], options.max_age,
                            options.max_paladin_age)


if __name__ == '__main__':
    main()
