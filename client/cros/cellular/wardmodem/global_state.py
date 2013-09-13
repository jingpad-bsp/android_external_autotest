# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import keyword
import logging
import re

import wardmodem_exceptions as wme

class GlobalStateSkeleton(collections.MutableMapping):
    """
    A skeleton to create global state.

    The global state should be an object of a derived class.

    To declare a new state component called dummy_var, with allowed values
    DUMMY_VAR_WOOF and DUMMY_VAR_POOF, add a call to
      self._add_state_component('dummy_var',
                                ['DUMMY_VAR_WOOF', 'DUMMY_VAR_POOF'])
    in __init__ of the derived class.

    Then any state machine that has the global state object, say gstate, can
    use the state component, viz,
      To read: my_state_has_val = gstate['dummy_var']
               my_state_has_val = gstate[gstate.dummy_var]  # preferred
      To write: gstate['dummy_var'] = 'DUMMY_VAR_WOOF'
                gstate[gstate.dummy_var] = gstate.DUMMY_VAR_WOOF  # preferred

    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        # A map to record the allowed values for each state component.
        self._allowed_values = {}
        # The map that stores the current values of all state components.
        self._values = {}

        # This value can be assigned to any state component to indicate invalid
        # value.
        # This is also the default value assigned when the state component is
        # added.
        self.INVALID_VALUE = 'INVALID_VALUE'


    def __getitem__(self, component):
        """
        Read current value of a state component.

        @param component: The component of interest.

        @return: String value of the state component.

        @raises: StateMachineException if the component does not exist.

        """
        if component not in self._values:
            self._runtime_error('Attempted to read value of unknown component: '
                                '|%s|' % component)
        return self._values[component]


    def __setitem__(self, component, value):
        """
        Write a new value to the specified state component.

        @param component: The component of interest.

        @param value: String value of the state component

        @raises: StateMachineException if the component does not exist, or if
                the value provided is not a valid value for the component.

        """
        if component not in self._values:
            self._runtime_error('Attempted to write value to unknown component:'
                                ' |%s|' % component)
        if value not in self._allowed_values[component]:
            self._runtime_error('Attempted to write invalid value |%s| to '
                                'component |%s|. Valid values are %s.' %
                                (value, component,
                                str(self._allowed_values[component])))
        self._logger.debug('GlobalState write: [%s: %s --> %s]',
                           component, self._values[component], value)
        self._values[component] = value


    def __delitem__(self, key):
        self.__runtime_error('Can not delete items from the global state')


    def __iter__(self):
        return iter(self._values)


    def __len__(self):
        return len(self._values)


    def __str__(self):
        return str(self._values)


    def __keytransform__(self, key):
        return key


    def _add_state_component(self, component_name, allowed_values):
        """
        Add a state component to the global state.

        @param component_name: The name of the newly created state component.
            Component names must be unique. Use lower case names.

        @param allowed_values: The list of string values that component_name can
                take. Use all-caps names / numbers.

        @raises: WardModemSetupException if the component_name exists or if an
                invalid value is requested to be allowed.

        @raises: TypeError if allowed_values is not a list.

        """
        # It is easy to pass in a string by mistake.
        if type(allowed_values) is not list:
            raise TypeError('allowed_values must be list of strings.')

        # Add component.
        if not re.match('[a-z][_a-z0-9]*$', component_name) or \
           keyword.iskeyword(component_name):
            self._setup_error('Component name ill-formed: |%s|' %
                              component_name)
        if component_name in self._values:
            self._setup_error('Component already exists: |%s|' % component_name)
        self._values[component_name] = self.INVALID_VALUE

        # Record allowed values.
        if self.INVALID_VALUE in allowed_values:
            self._setup_error('%s can not be an allowed value.' %
                              self.INVALID_VALUE)
        for allowed_value in allowed_values:
            if isinstance(allowed_value, str):
                if not re.match('[_A-Z0-9]*$', allowed_value) or \
                        keyword.iskeyword(component_name):
                    self._setup_error('Allowed value ill-formed: |%s|' %
                                     allowed_value)
        self._allowed_values[component_name] = set(allowed_values)


    def _setup_error(self, errstring):
        """
        Log the error and raise WardModemSetupException.

        @param errstring: The error string.

        """
        self._logger.error(errstring)
        raise wme.WardModemSetupException(errstring)


    def _runtime_error(self, errstring):
        """
        Log the error and raise StateMachineException.

        @param errstring: The error string.

        """
        self._logger.error(errstring)
        raise wme.StateMachineException(errstring)


class GlobalState(GlobalStateSkeleton):
    """
    All global state is stored in this object.

    This class fills-in state components in the GlobalStateSkeleton.

    @see GlobalStateSkeleton

    """

    def __init__(self):
        super(GlobalState, self).__init__()
        # TODO(pprabhu) Now, add all state components.
