# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions for AFE-based interactions."""

import common
from autotest_lib.server import utils
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers

AFE = frontend_wrappers.RetryingAFE(timeout_min=5, delay_sec=10)


def host_in_lab(host):
    """Check if the host is in the lab and an object the AFE knows.

    This check ensures that autoserv and the host's current job is running
    inside a fully Autotest instance, aka a lab environment. If this is the
    case it then verifies the host is registed with the configured AFE
    instance.

    @param host: Host object to verify.

    @returns The host model object.
    """
    if not host.job.in_lab:
        return False
    return AFE.get_hosts(hostname=host.hostname)


def get_build(host):
    """Retrieve the current build for a given hostname from the AFE.

    Looks through a host's labels in the AFE to determine its build.

    @param hostname: Hostname of the host whose build we want to retrieve.

    @returns The current build or None if it could not find it or if there
             were multiple build labels assigned to the host.
    """
    if not host_in_lab(host):
        return None
    return utils.get_build_from_afe(host.hostname, AFE)


def clear_version_labels(host):
    """Clear version labels for a given host.

    @param host: Host whose version labels to clear.
    """
    if not host_in_lab(host):
        return

    host_list = [host.hostname]
    labels = AFE.get_labels(
            name__startswith=host.VERSION_PREFIX,
            host__hostname=host.hostname)

    for label in labels:
        label.remove_hosts(hosts=host_list)


def add_version_label(host, image_name):
    """Add version labels to a host.

    @param host: Host to add the version label for.
    @param image_name: Name of the build version to add to the host.
    """
    if not host_in_lab(host):
        return
    label = '%s:%s' % (host.VERSION_PREFIX, image_name)
    AFE.run('label_add_hosts', id=label, hosts=[host.hostname])


def machine_install_and_update_labels(host, *args, **dargs):
    """Calls machine_install and updates the version labels on a host.

    @param host: Host object to run machine_install on.
    @param *args: Args list to pass to machine_install.
    @param **dargs: dargs dict to pass to machine_install.
    """
    clear_version_labels(host)
    image_name = host.machine_install(*args, **dargs)
    add_version_label(host, image_name)
