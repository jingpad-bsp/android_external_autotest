# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import abc
import logging

import common
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.server import frontend


### Constants for label prefixes
CROS_VERSION_PREFIX = 'cros-version'
FW_VERSION_PREFIX = 'fw-version'


### Helpers to convert value to label
def cros_version_to_label(image):
    """
    Returns the proper label name for a ChromeOS build of |image|.

    @param image: A string of the form 'lumpy-release/R28-3993.0.0'
    @returns: A string that is the appropriate label name.

    """
    return CROS_VERSION_PREFIX + ':' + image


class _SpecialTaskAction(object):
    """
    Base class to give a template for mapping labels to tests.
    """

    __metaclass__ = abc.ABCMeta


    # One cannot do
    #     @abc.abstractproperty
    #     _actions = {}
    # so this is the next best thing
    @abc.abstractproperty
    def _actions(self):
        """A dictionary mapping labels to test names."""
        pass


    @abc.abstractproperty
    def name(self):
        """The name of this special task to be used in output."""
        pass


    @classmethod
    def acts_on(cls, label):
        """
        Returns True if the label is a label that we recognize as something we
        know how to act on, given our _actions.

        @param label: The label as a string.
        @returns: True if there exists a test to run for this label.

        """
        return label.split(':')[0] in cls._actions


    @classmethod
    def test_for(cls, label):
        """
        Returns the test associated with the given (string) label name.

        @param label: The label for which the action is being requested.
        @returns: The string name of the test that should be run.
        @raises KeyError: If the name was not recognized as one we care about.

        """
        return cls._actions[label]


class Verify(_SpecialTaskAction):
    """
    Tests to verify that the DUT is in a sane, known good state that we can run
    tests on.  Failure to verify leads to running Repair.
    """

    _actions = {
    }

    name = 'verify'


class Provision(_SpecialTaskAction):
    """
    Provisioning runs to change the configuration of the DUT from one state to
    another.  It will only be run on verified DUTs.
    """

    # TODO(milleral): http://crbug.com/249555
    # Create some way to discover and register provisioning tests so that we
    # don't need to hand-maintain a list of all of them.
    _actions = {
        CROS_VERSION_PREFIX: 'provision_AutoUpdate',
        FW_VERSION_PREFIX: 'provision_FirmwareUpdate',
    }

    name = 'provision'


class Cleanup(_SpecialTaskAction):
    """
    Cleanup runs after a test fails to try and remove artifacts of tests and
    ensure the DUT will be in a sane state for the next test run.
    """

    _actions = {
    }

    name = 'cleanup'


class Repair(_SpecialTaskAction):
    """
    Repair runs when one of the other special tasks fails.  It should be able
    to take a component of the DUT that's in an unknown state and restore it to
    a good state.
    """

    _actions = {
    }

    name = 'repair'


# For backwards compatibility with old control files, we still need the
# following:

can_provision = Provision.acts_on
provisioner_for = Provision.test_for


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


def join(provision_type, provision_value):
    """
    Combine the provision type and value into the label name.

    @param provision_type: One of the constants that are the label prefixes.
    @param provision_value: A string of the value for this provision type.
    @returns: A string that is the label name for this (type, value) pair.

    >>> join(CROS_VERSION_PREFIX, 'lumpy-release/R27-3773.0.0')
    'cros-version:lumpy-release/R27-3773.0.0'

    """
    return '%s:%s' % (provision_type, provision_value)


# This has been copied out of dynamic_suite's reimager.py, which no longer
# exists.  I'd prefer if this would go away by doing http://crbug.com/249424,
# so that labels are just automatically made when we try to add them to a host.
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
