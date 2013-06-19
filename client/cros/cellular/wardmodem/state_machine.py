# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import keyword
import logging
import re

import task_loop
import wardmodem_exceptions as wme

class StateMachine(object):
    """
    Base class for all state machines in wardmodem.

    """

    def __init__(self, state, transceiver):
        """
        @param state: The GlobalState object shared by all state machines.

        @param transceiver: The ATTransceiver object to interact with.

        @raises: SetupException if we attempt to create an instance of a machine
        that has not been completely specified (see get_well_known_name).

        """
        self._state = state
        self._transceiver = transceiver

        self._logger = logging.getLogger(__name__)
        self._task_loop = task_loop.get_instance()

        self._state_update_tag = 0  # Used to tag logs of async updates to
                                    # state.

        # Will raise an exception if this machine should not be instantiated.
        self.get_well_known_name()

    # ##########################################################################
    # Subclasses must override these.

    def get_well_known_name(self):
        """
        A well know name of the completely specified state machine.

        The first derived class that completely specifies some state machine
        should implement this function to return its own type.

        """
        # Do not use self._setup_error because it causes infinite recursion.
        raise wme.WardModemSetupException(
                'Attempted to get well known name for a state machine that is '
                'not completely specified.')

    # ##########################################################################
    # Protected convenience methods to be used as is by subclasses.

    def _respond(self, response, response_delay_ms, *response_args):
        """
        Respond to the modem after some delay.

        @param reponse: String response. This must be one of the response
                strings recognized by ATTransceiver.

        @param response_delay_ms: Delay in milliseconds after which the response
                should be sent. Type: int.

        @param *response_args: The arguments for the response.

        @requires: response_delay_ms > 0

        """
        assert response_delay_ms >= 0
        dbgstr = self._tag_with_name(
                'Will respond with "%s(%s)" after %d ms.' %
                (response, str(response_args), response_delay_ms))
        self._logger.debug(dbgstr)
        self._task_loop.post_task(self._transceiver.process_wardmodem_response,
                                  response_delay_ms, response, *response_args)


    def _update_state(self, state_update, state_update_delay_ms):
        """
        Post a (delayed) state update.

        @param state_update: The state update to apply. This is a map {string
                --> state enum} that specifies all the state components to be
                updated.

        @param state_update_delay_ms: Delay in milliseconds after which the
                state update should be applied. Type: int.

        @requires: state_update_delay_ms > 0

        """
        assert state_update_delay_ms > 0
        dbgstr = self._tag_with_name(
                '[tag:%d] Will update state as %s after %d ms.' %
                (self._state_update_tag, str(state_update),
                 state_update_delay_ms))
        self._logger.debug(dbgstr)
        self._task_loop.post_task(self._update_state_callback,
                                  state_update_delay_ms, state_update,
                                  self._state_update_tag)
        self._state_update_tag += 1


    def _update_state_and_respond(self, state_update, state_update_delay_ms,
                                  response, response_delay_ms, *response_args):
        """
        Respond to the modem after some delay, and also update state.

        @param state_update: The state update to apply. This is a map {string
                --> state enum} that specifies all the state components to be
                updated.

        @param state_update_delay_ms: Delay in milliseconds after which the
                state update should be applied. Type: int.

        @param response: String response. This must be one of the response
                strings recognized by ATTransceiver.

        @param response_delay_ms: Delay in milliseconds after which the response
                should be sent. Type: int.

        @param response_args: The arguments for the response.

        @requires: response_delay_ms > state_update_delay_ms > 0

        """
        assert response_delay_ms > state_update_delay_ms > 0
        dbgstr = self._tag_with_name(
                '[tag:%d] Will update state as %s after %d ms; '
                'Will respond %s(%s) after %d ms.' %
                (self._state_update_tag, str(state_update),
                 state_update_delay_ms, response, str(response_args),
                 response_delay_ms))
        self._logger.debug(dbgstr)
        self._task_loop.post_task(self._update_state_callback,
                                  state_update_delay_ms, state_update,
                                  self._state_update_tag)
        self._state_update_tag += 1
        self._task_loop.post_task(self._transceiver.process_wardmodem_response,
                                  response_delay_ms, response, *response_args)


    def _add_response_function(self, function):
        """
        Add a response used by this state machine to send to the ATTransceiver.

        A state machine should register all the responses it will use in its
        __init__ function by calling
            self._add_response_function('wm_response_dummy')
        The response can then be used to respond to the transceiver thus:
            self._respond(self.wm_response_dummy)

        @param function: The string function name to add. Must be a valid python
                identifier in lowercase.
                Also, these names are conventionally named matching the re
                'wm_response_([a-z0-9]*[_]?)*'

        @raises: WardModemSetupError if the added response function is ill
                formed.

        """
        if not re.match('wm_response_([a-z0-9]*[_]?)*', function) or \
           keyword.iskeyword(function):
            self._setup_error('Response function name ill-formed: |%s|' %
                              function)
        try:
            getattr(self, function)
            self._setup_error('Attempted to add response function %s which '
                              'already exists.' % function)
        except AttributeError:  # OK, This is the good case.
            setattr(self, function, function)


    def _setup_error(self, errstring):
        """
        Log the error and raise WardModemSetupException.

        @param errstring: The error string.

        """
        errstring = self._tag_with_name(errstring)
        self._logger.error(errstring)
        raise wme.WardModemSetupException(errstring)


    def _runtime_error(self, errstring):
        """
        Log the error and raise StateMachineException.

        @param errstring: The error string.

        """
        errstring = self._tag_with_name(errstring)
        self._logger.error(errstring)
        raise wme.StateMachineException(errstring)

    def _tag_with_name(self, log_string):
        """
        If possible, prepend the log string with the well know name of the
        object.

        @param log_string: The string to modify.

        @return: The modified string.

        """
        name = self.get_well_known_name()
        log_string = '[' + name + '] ' + log_string
        return log_string

    # ##########################################################################
    # Private methods not to be used by subclasses.

    def _update_state_callback(self, state_update, tag):
        """
        Actually update the state.

        @param state_update: The state update to effect. This is a map {string
                --> state enum} that specifies all the state components to be
                updated.

        @param tag: The tag for this state update.

        @raises: StateMachineException if the state update fails.

        """
        dbgstr = self._tag_with_name('[tag:%d] State update applied.')
        self._logger.debug(dbgstr)
        for component, value in state_update:
            self._state[component] = value
