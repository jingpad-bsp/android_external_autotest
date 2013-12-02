#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to stage servo image and full payload in all devservers.

This script should be executed in a server running autotest scheduler. It is
used to accomplish following tasks:
1. Get the latest staged build in devserver as the build that's currently used
by servo.
2. Stage the latest or a specified beaglebone build from Google Storage
in all devservers.
3. Show an error if a specified build was successfully staged, but a devserver
has newer build staged.

"""

import argparse
import logging
import sys

import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
from devserver import gsutil_util


DEFAULT_BUILD_TARGET = 'beaglebone-release'
IMAGE_STORAGE_SERVER = global_config.global_config.get_config_value('CROS',
        'image_storage_server', type=str)


def get_all_devservers():
    """Get a list of ImageServer objects for all available devservers.

    @return: A list of ImageServer objects for all available devservers.
    """
    return [dev_server.ImageServer(server) for server in
            dev_server._get_dev_server_list()]


def get_latest_build(build_target):
    """Get the latest build of beaglebone image in Google Storage.

    @param build_target: build target to look up for the latest build.
    @return: build name of latest beaglebone image in Google Storage,
             e.g., beaglebone-release/R33-4936.0.0
    """
    archive_url = IMAGE_STORAGE_SERVER + build_target
    return gsutil_util.GetLatestVersionFromGSDir(archive_url)


def stage_build(devserver, build, build_target=DEFAULT_BUILD_TARGET):
    """Stage build and its respective image in a devserver

    @param devserver: an instance of ImageServer.
    @param build: name of the beaglebone build to stage, e.g., R33-4936.0.0.
    @param build_target: build target of the build to be staged, default
                         is set to beaglebone-release.
    @raise DevServerException: upon any return code that's not HTTP OK when
                               making stage_artifacts RPC.
    """
    image = '%s/%s' % (build_target, build)
    # Stage base_image will download image.zip,
    # unzip chromiumos_base_image.tar.xz, which contains
    # chromiumos_base_image.bin.
    artifacts = ['full_payload', 'base_image']
    logging.info('Staging %s using devserver %s...', image, devserver.url())
    devserver.stage_artifacts(image=image, artifacts=artifacts)
    logging.info('Staging completed successfully.')


def parse_arguments(argv):
    """
    Parse command line arguments

    @param argv: argument list to parse
    @returns:    parsed arguments.
    @raises SystemExit if arguments are malformed, or required arguments
            are not present.
    """
    description = 'Stage latest or a specific build at all devservers.'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-i', '--build', action='store', default=None,
                        help='Optional argument to specify a build to stage, '
                             'e.g., R33-5079.0.0. Do not include the build '
                             'target here.')
    parser.add_argument('-t', '--build_target', action='store',
                        default=DEFAULT_BUILD_TARGET,
                        help='Optional argument to specify a build target, '
                             'e.g., trybot-beaglebone-release. Default value '
                             'is set to beaglebone-release.')
    return parser.parse_args(argv)


def main(argv):
    """Main entrance of the script.

    @param argv: arguments list
    """
    arguments = parse_arguments(argv)
    build_target = arguments.build_target
    devservers = get_all_devservers()
    if not devservers:
        raise Exception('No devserver found. Script failed to stage any build. '
                        'Please check your shadow_config.ini file about '
                        'devserver setting.')

    if arguments.build:
        build_to_stage = arguments.build
    else:
        build_to_stage = get_latest_build(build_target)
        logging.info('Latest build for %s is %s.', build_target, build_to_stage)

    try:
        # The build must be staged in all devservers. Any devserver failed to
        # stage the build shall fail the script. When in prod, a beaglebone may
        # hit any available devserver to update the latest image staged in the
        # devserver, without requesting to stage the build. That's why it's
        # essential for all devservers to have the same build staged.
        for devserver in devservers:
            stage_build(devserver, build_to_stage, build_target)
    except dev_server.DevServerException as e:
        logging.error('Staging build %s failed with error: \n%s',
                      build_to_stage, e)
        # Check if latest_staged_builds are all the same, if so, delete any
        # staged |build_to_stage| in all devservers.
        latest_staged_builds = [devserver.get_latest_build_in_server(
                build_target) for devserver in devservers]
        if not all(b == latest_staged_builds[0] for b in latest_staged_builds):
            logging.error(('devservers have different latest builds for build '
                           'target %s. You should try to fix the problem, and '
                           'run this script again to make sure all devservers '
                           'have the same latest build staged.'), build_target)
        sys.exit(1)

    # Save the latest build in each devserver in a list, will be used to check
    # if they are newer builds compared to the build to be staged.
    latest_staged_builds = [devserver.get_latest_build_in_server(build_target)
                            for devserver in devservers]

    # Compare the previous latest build staged in devserver and build_to_stage.
    # If the previous latest builder is newer, post a warning that user should
    # manually delete any newer builds in each devserver.
    if not all(b == build_to_stage for b in latest_staged_builds):
        logging.error('Following devservers have staged newer build. You need '
                      'to manually delete any build newer than %s in each '
                      'devserver to guarantee beaglebone can be upgraded to the'
                      ' desired build.\n', build_to_stage)

    for devserver, build in zip(devservers, latest_staged_builds):
        if build != build_to_stage:
            logging.error('%s\t%s', devserver.url(), build)


if __name__ == '__main__':
    main(sys.argv[1:])
