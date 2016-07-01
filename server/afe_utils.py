# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions for AFE-based interactions.

NOTE: This module should only be used in the context of a running test. Any
      utilities that require accessing the AFE, should do so by creating
      their own instance of the AFE client and interact with it directly.
"""

import common
from autotest_lib.client.common_lib import error
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
    if not host.job or not host.job.in_lab:
        return False
    return AFE.get_hosts(hostname=host.hostname)


def get_build(host):
    """Retrieve the current build for a given host from the AFE.

    Looks through a host's labels in the AFE to determine its build.

    @param host: Host object to get build.

    @returns The current build or None if it could not find it or if there
             were multiple build labels assigned to the host.
    """
    if not host_in_lab(host):
        return None
    return utils.get_build_from_afe(host.hostname, AFE)


def get_board(host):
    """Retrieve the board for a given host from the AFE.

    Contacts the AFE to retrieve the board for a given host.

    @param host: Host object to get board.

    @returns The current board or None if it could not find it.
    """
    if not host_in_lab(host):
        return None
    return utils.get_board_from_afe(host.hostname, AFE)


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


def get_stable_version(board, android=False):
    """Retrieves a board's stable version from the AFE.

    @param board: Board to lookup.
    @param android: If True, indicates we are looking up a Android/Brillo-based
                    board. There is no default version that works for all
                    Android/Brillo boards. If False, we are looking up a Chrome
                    OS based board.

    @returns Stable version of the given board.
    """
    return AFE.run('get_stable_version', board=board, android=android)


def lookup_job_repo_url(host):
    """Looks up the job_repo_url for the host.

    The method is kept for backwards compatibility with test
    autoupdate_EndToEndTest in existing builds. It should not be used for new
    code.
    TODO(dshi): Update autoupdate_EndToEndTest to use get_host_attribute after
    lab is updated. After R50 is in stable channel, this method can be removed.

    @param host: A Host object to lookup for job_repo_url.

    @returns Host attribute `job_repo_url` of the given host.
    """
    return get_host_attribute(host, host.job_repo_url_attribute)


def get_host_attribute(host, attribute):
    """Looks up the value of host attribute for the host.

    @param host: A Host object to lookup for attribute value.
    @param attribute: Name of the host attribute.

    @returns value for the given attribute or None if not found.
    """
    local_value = host.host_attributes.get(attribute)
    if not host_in_lab(host):
        return local_value

    hosts = AFE.get_hosts(hostname=host.hostname)
    if hosts and attribute in hosts[0].attributes:
        return hosts[0].attributes[attribute]
    else:
        return local_value


def clear_host_attributes_before_provision(host):
    """Clear host attributes before provision, e.g., job_repo_url.

    @param host: A Host object to clear attributes before provision.
    """
    attributes = host.get_attributes_to_clear_before_provision()
    for attribute in attributes:
        if attribute in host.host_attributes:
            del host.host_attributes[attribute]
    if not host_in_lab(host):
        return

    for attribute in attributes:
        update_host_attribute(host, attribute, None)


def update_host_attribute(host, attribute, value):
    """Updates the host attribute with given value.

    @param host: A Host object to update attribute value.
    @param attribute: Name of the host attribute.
    @param value: Value for the host attribute.

    @raises AutoservError: If we failed to update the attribute.
    """
    host.host_attributes[attribute] = value
    if not host_in_lab(host):
        return

    AFE.set_host_attribute(attribute, value, hostname=host.hostname)
    if get_host_attribute(host, attribute) != value:
        raise error.AutoservError(
                'Failed to update host attribute `%s` with %s, host %s' %
                (attribute, value, host.hostname))


def machine_install_and_update_labels(host, *args, **dargs):
    """Calls machine_install and updates the version labels on a host.

    @param host: Host object to run machine_install on.
    @param *args: Args list to pass to machine_install.
    @param **dargs: dargs dict to pass to machine_install.
    """
    clear_version_labels(host)
    clear_host_attributes_before_provision(host)
    image_name, host_attributes = host.machine_install(*args, **dargs)
    add_version_label(host, image_name)
    for attribute, value in host_attributes.items():
        update_host_attribute(host, attribute, value)


def get_labels(host, prefix):
    """Get labels of a host with name started with given prefix.

    @param prefix: Prefix of label names.
    """
    return AFE.get_labels(name__startswith=prefix, host__hostname=host.hostname)


def get_os(host):
    """Retrieve the os for a given host from the AFE.

    Contacts the AFE to retrieve the os for a given host.

    @param host: Host object to get board.

    @returns The os or None if it could not find it.
    """
    if not host_in_lab(host):
        return None
    return utils.get_label_from_afe(host.hostname, 'os:', AFE)
