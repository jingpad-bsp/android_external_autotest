# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import re
import sys

import common
from autotest_lib.server.cros import provision_actionables as actionables


### Constants for label prefixes
CROS_VERSION_PREFIX = 'cros-version'
ANDROID_BUILD_VERSION_PREFIX = 'ab-version'
TESTBED_BUILD_VERSION_PREFIX = 'testbed-version'
FW_RW_VERSION_PREFIX = 'fwrw-version'
FW_RO_VERSION_PREFIX = 'fwro-version'

# Special label to skip provision and run reset instead.
SKIP_PROVISION = 'skip_provision'

# Default number of provisions attempts to try if we believe the devserver is
# flaky.
FLAKY_DEVSERVER_ATTEMPTS = 2


def label_from_str(label_string):
    """Return a proper Label instance from a label string.

    This function is for converting an existing label string into a Label
    instance of the proper type.  For constructing a specific type of label,
    don't use this.  Instead, instantiate the specific Label subclass.

    @param label_string: Label string.
    @returns: An instance of Label or a subclass.
    """
    if NamespaceLabel.SEP in label_string:
        label = NamespaceLabel.from_str(label_string)
        namespaces = _PresetNamespaceLabelMeta.namespaces
        if label.namespace in namespaces:
            return namespaces[label.namespace](label.value)
        else:
            return label
    else:
        return Label(label_string)


class Label(str):
    """A string that is explicitly typed as a label."""

    def __repr__(self):
        return '{cls}({label})'.format(
            cls=type(self).__name__,
            label=super(Label, self).__repr__())

    @property
    def action(self):
        """Return the action represented by the label.

        This is used for determine actions to perform based on labels, for
        example for provisioning or repair.

        @return: An Action instance.
        """
        return Action(self, '')


Action = collections.namedtuple('Action', 'name,value')


class NamespaceLabel(Label):
    """Label with namespace and value separated by a colon."""

    SEP = ':'

    def __new__(cls, namespace, value):
        return super(NamespaceLabel, cls).__new__(
            cls, cls.SEP.join((namespace, value)))

    @classmethod
    def from_str(cls, label):
        """Make NamespaceLabel instance from full string.

        @param label: Label string.
        @returns: NamespaceLabel instance.
        """
        namespace, value = label.split(cls.SEP, 1)
        return cls(namespace, value)

    @property
    def namespace(self):
        """The label's namespace (before colon).

        @returns: string
        """
        return self.split(self.SEP, 1)[0]

    @property
    def value(self):
        """The label's value (after colon).

        @returns: string
        """
        return self.split(self.SEP, 1)[1]

    @property
    def action(self):
        """Return the action represented by the label.

        See docstring on overridden method.

        @return: An Action instance.
        """
        return Action(self.namespace, self.value)


class _PresetNamespaceLabelMeta(type):
    """Metaclass for PresetNamespaceLabelMeta and subclasses.

    This automatically tracks the NAMESPACE for concrete classes that define
    it.  The namespaces attribute is a dict mapping namespace strings to the
    corresponding NamespaceLabel subclass.
    """

    namespaces = {}

    def __init__(cls, name, bases, dict_):
        if hasattr(cls, 'NAMESPACE'):
            type(cls).namespaces[cls.NAMESPACE] = cls


class _PresetNamespaceLabel(NamespaceLabel):
    """NamespaceLabel with preset namespace.

    This class is abstract.  Concrete subclasses must set a NAMESPACE class
    attribute.
    """

    __metaclass__ = _PresetNamespaceLabelMeta

    def __new__(cls, value):
        return super(_PresetNamespaceLabel, cls).__new__(cls, cls.NAMESPACE, value)


class CrosVersionLabel(_PresetNamespaceLabel):
    """cros-version label."""
    NAMESPACE = CROS_VERSION_PREFIX

    @property
    def value(self):
        """The label's value (after colon).

        @returns: string
        """
        return CrosVersion(super(CrosVersionLabel, self).value)


class FWROVersionLabel(_PresetNamespaceLabel):
    """Read-only firmware version label."""
    NAMESPACE = FW_RO_VERSION_PREFIX


class FWRWVersionLabel(_PresetNamespaceLabel):
    """Read-write firmware version label."""
    NAMESPACE = FW_RW_VERSION_PREFIX


class CrosVersion(str):
    """The name of a CrOS image version (e.g. lumpy-release/R27-3773.0.0).

    Parts of the image name are exposed via properties.  In case the name is
    not well-formed, these properties return INVALID_STR, which is not a valid value
    for any part.

    Class attributes:
        INVALID_STR -- String returned if the version is not well-formed.

    Properties:
        group
        milestone
        version
        rc
    """

    INVALID_STR = 'N/A'
    _NAME_PATTERN = re.compile(
        r'^'
        r'(?P<group>[a-z0-9-]+)'
        r'/'
        r'(?P<milestone>R[0-9]+)'
        r'-'
        r'(?P<version>[0-9.]+)'
        r'(-(?P<rc>rc[0-9]+))?'
        r'$'
    )

    def __repr__(self):
        return '{cls}({name})'.format(
            cls=type(self).__name__,
            name=super(CrosVersion, self).__repr__())

    def _get_group(self, group):
        """Get regex match group, or fall back to N/A.

        @param group: Group name string.
        @returns String.
        """
        match = self._NAME_PATTERN.search(self)
        if match is None:
            return self.INVALID_STR
        else:
            return match.group(group)

    @property
    def group(self):
        """Cros image group (e.g. lumpy-release)."""
        return self._get_group('group')

    @property
    def milestone(self):
        """Cros image milestone (e.g. R27)."""
        return self._get_group('milestone')

    @property
    def version(self):
        """Cros image milestone (e.g. 3773.0.0)."""
        return self._get_group('version')

    @property
    def rc(self):
        """Cros image rc (e.g. rc2)."""
        return self._get_group('rc')


class _SpecialTaskAction(object):
    """
    Base class to give a template for mapping labels to tests.
    """

    # A dictionary mapping labels to test names.
    _actions = {}

    # The name of this special task to be used in output.
    name = None;

    # Some special tasks require to run before others, e.g., ChromeOS image
    # needs to be updated before firmware provision. List `_priorities` defines
    # the order of each label prefix. An element with a smaller index has higher
    # priority. Not listed ones have the lowest priority.
    # This property should be overriden in subclass to define its own priorities
    # across available label prefixes.
    _priorities = []

    @classmethod
    def acts_on(cls, label_string):
        """
        Returns True if the label is a label that we recognize as something we
        know how to act on, given our _actions.

        @param label_string: The label as a string.
        @returns: True if there exists a test to run for this label.
        """
        label = label_from_str(label_string)
        return label.action.name in cls._actions

    @classmethod
    def test_for(cls, label):
        """
        Returns the test associated with the given (string) label name.

        @param label: The label for which the action is being requested.
        @returns: The string name of the test that should be run.
        @raises KeyError: If the name was not recognized as one we care about.
        """
        return cls._actions[label]

    @classmethod
    def partition(cls, labels):
        """
        Filter a list of labels into two sets: those labels that we know how to
        act on and those that we don't know how to act on.

        @param labels: A list of strings of labels.
        @returns: A tuple where the first element is a set of unactionable
                  labels, and the second element is a set of the actionable
                  labels.
        """
        capabilities = set()
        configurations = set()

        for label in labels:
            if label == SKIP_PROVISION:
                # skip_provision is neither actionable or a capability label.
                # It doesn't need any handling.
                continue
            elif cls.acts_on(label):
                configurations.add(label)
            else:
                capabilities.add(label)

        return capabilities, configurations

    @classmethod
    def get_sorted_actions(cls, configurations):
        """
        Sort configurations based on the priority defined in cls._priorities.

        @param configurations: A list of actionable labels.
        @return: A list of Action instances sorted by the action name in
            cls._priorities.
        """
        actions = (label_from_str(label_string).action
                   for label_string in configurations)
        return sorted(actions, key=cls._get_action_priority)

    @classmethod
    def _get_action_priority(cls, action):
        """
        Return the priority of the action string.

        @param action: An Action instance.
        @return: An int.
        """
        if action.name in cls._priorities:
            return cls._priorities.index(action.name)
        else:
            return sys.maxint


class Verify(_SpecialTaskAction):
    """
    Tests to verify that the DUT is in a sane, known good state that we can run
    tests on.  Failure to verify leads to running Repair.
    """

    _actions = {
        'modem_repair': actionables.TestActionable('cellular_StaleModemReboot'),
        # TODO(crbug.com/404421): set rpm action to power_RPMTest after the RPM
        # is stable in lab (destiny). The power_RPMTest failure led to reset job
        # failure and that left dut in Repair Failed. Since the test will fail
        # anyway due to the destiny lab issue, and test retry will retry the
        # test in another DUT.
        # This change temporarily disable the RPM check in reset job.
        # Another way to do this is to remove rpm dependency from tests' control
        # file. That will involve changes on multiple control files. This one
        # line change here is a simple temporary fix.
        'rpm': actionables.TestActionable('dummy_PassServer'),
    }

    name = 'verify'


class Provision(_SpecialTaskAction):
    """
    Provisioning runs to change the configuration of the DUT from one state to
    another.  It will only be run on verified DUTs.
    """

    # ChromeOS update must happen before firmware install, so the dut has the
    # correct ChromeOS version label when firmware install occurs. The ChromeOS
    # version label is used for firmware update to stage desired ChromeOS image
    # on to the servo USB stick.
    _priorities = [CROS_VERSION_PREFIX,
                   FW_RO_VERSION_PREFIX,
                   FW_RW_VERSION_PREFIX]

    # TODO(milleral): http://crbug.com/249555
    # Create some way to discover and register provisioning tests so that we
    # don't need to hand-maintain a list of all of them.
    _actions = {
        CROS_VERSION_PREFIX: actionables.TestActionable(
                'provision_AutoUpdate',
                extra_kwargs={'disable_sysinfo': False,
                              'disable_before_test_sysinfo': False,
                              'disable_before_iteration_sysinfo': True,
                              'disable_after_test_sysinfo': True,
                              'disable_after_iteration_sysinfo': True}),
        FW_RO_VERSION_PREFIX: actionables.TestActionable(
                'provision_FirmwareUpdate'),
        FW_RW_VERSION_PREFIX: actionables.TestActionable(
                'provision_FirmwareUpdate',
                extra_kwargs={'rw_only': True,
                              'tag': 'rw_only'}),
        ANDROID_BUILD_VERSION_PREFIX : actionables.TestActionable(
                'provision_AndroidUpdate'),
        TESTBED_BUILD_VERSION_PREFIX : actionables.TestActionable(
                'provision_TestbedUpdate'),
    }

    name = 'provision'


class Cleanup(_SpecialTaskAction):
    """
    Cleanup runs after a test fails to try and remove artifacts of tests and
    ensure the DUT will be in a sane state for the next test run.
    """

    _actions = {
        'cleanup-reboot': actionables.RebootActionable(),
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


# TODO(milleral): crbug.com/364273
# Label doesn't really mean label in this context.  We're putting things into
# DEPENDENCIES that really aren't DEPENDENCIES, and we should probably stop
# doing that.
def is_for_special_action(label):
    """
    If any special task handles the label specially, then we're using the label
    to communicate that we want an action, and not as an actual dependency that
    the test has.

    @param label: A string label name.
    @return True if any special task handles this label specially,
            False if no special task handles this label.
    """
    return (Verify.acts_on(label) or
            Provision.acts_on(label) or
            Cleanup.acts_on(label) or
            Repair.acts_on(label) or
            label == SKIP_PROVISION)


class SpecialTaskActionException(Exception):
    """
    Exception raised when a special task fails to successfully run a test that
    is required.

    This is also a literally meaningless exception.  It's always just discarded.
    """


def run_special_task_actions(job, host, labels, task):
    """
    Iterate through all `label`s and run any tests on `host` that `task` has
    corresponding to the passed in labels.

    Emits status lines for each run test, and INFO lines for each skipped label.

    @param job: A job object from a control file.
    @param host: The host to run actions on.
    @param labels: The list of job labels to work on.
    @param task: An instance of _SpecialTaskAction.
    @returns: None
    @raises: SpecialTaskActionException if a test fails.

    """
    capabilities, configurations = task.partition(labels)

    for label in capabilities:
        job.record('INFO', None, task.name,
                   "Can't %s label '%s'." % (task.name, label))

    # Sort the configuration labels based on `task._priorities`.
    actions = task.get_sorted_actions(configurations)
    for name, value in actions:
        action_item = task.test_for(name)
        success = action_item.execute(job=job, host=host, value=value)
        if not success:
            raise SpecialTaskActionException()
