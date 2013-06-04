# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging

import common
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.server import frontend


### Constants for label prefixes
CROS_VERSION_PREFIX = 'cros-version'


### Helpers to convert value to label
def cros_version_to_label(image):
    """
    Returns the proper label name for a ChromeOS build of |image|.

    @param image: A string of the form 'lumpy-release/R28-3993.0.0'
    @returns: A string that is the appropriate label name.

    """
    return CROS_VERSION_PREFIX + ':' + image


# TODO(milleral): http://crbug.com/249555
# Create some way to discover and register provisioning tests so that we don't
# need to hand-maintain a list of all of them.
_provision_types = {
    CROS_VERSION_PREFIX:'provision_AutoUpdate',
}


def can_provision(label):
    """
    Returns True if the label is a label that we recognize as something we
    know how to provision.

    @param label: The label as a string.
    @returns: True if there exists a test to provision the label.

    """
    return label.split(':')[0] in _provision_types


def provisioner_for(name):
    """
    Returns the provisioning class associated with the given (string) name.

    @param name: The name of the provision type being requested.
    @returns: The subclass of Provisioner that was requested.
    @raises KeyError: If the name was not recognized as a provision type.

    """
    return _provision_types[name]


def filter_labels(labels):
    """
    Filter a list of labels into two sets: those labels that we know how to
    change and those that we don't.  For the ones we know how to change, split
    them apart into the name of configuration type and its value.

    @param labels: A list of strings of labels.
    @returns: A tuple where the first element is a set of unprovisionable
              labels, and the second element is a set of the provisionable
              labels.

    >>> filter_labels(['bluetooth', 'cros-version:lumpy-release/R28-3993.0.0'])
    (set(['bluetooth']), set(['cros-version:lumpy-release/R28-3993.0.0']))

    """
    capabilities = set()
    configurations = set()

    for label in labels:
        if can_provision(label):
            configurations.add(label)
        else:
            capabilities.add(label)

    return capabilities, configurations


def split_labels(labels):
    """
    Split a list of labels into a dict mapping name to value.  All labels must
    be provisionable labels, or else a ValueError

    @param labels: list of strings of label names
    @returns: A dict of where the key is the configuration name, and the value
              is the configuration value.
    @raises: ValueError if a label is not a provisionable label.

    >>> split_labels(['cros-version:lumpy-release/R28-3993.0.0'])
    {'cros-version': 'lumpy-release/R28-3993.0.0'}
    >>> split_labels(['bluetooth'])
    Traceback (most recent call last):
    ...
    ValueError: Unprovisionable label bluetooth

    """
    configurations = dict()

    for label in labels:
        if can_provision(label):
            name, value = label.split(':', 1)
            configurations[name] = value
        else:
            raise ValueError('Unprovisionable label %s' % label)

    return configurations


# This has been copied out of dynamic_suite's reimager.py, which will be killed
# off in a future CL.  I'd prefer if this would go away by doing
# http://crbug.com/249424, so that labels are just automatically made when we
# try to add them to a host.
def ensure_label_exists(name):
    """
    Ensure that a label called |name| exists in the autotest DB.

    @param name: the label to check for/create.
    @raises ValidationError: There was an error in the response that was
                             not because the label already existed.

    """
    afe = frontend.AFE()
    try:
        afe.create_label(name=name)
    except proxy.ValidationError as ve:
        if ('name' in ve.problem_keys and
            'This value must be unique' in ve.problem_keys['name']):
            logging.debug('Version label %s already exists', name)
        else:
            raise ve
