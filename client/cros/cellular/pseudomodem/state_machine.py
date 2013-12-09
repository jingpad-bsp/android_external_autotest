# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gobject
import logging
import mm1

class StateMachine(object):
    """
    StateMachine is the abstract base class for the complex state machines
    that are involved in the pseudo modem manager.

    Every state transition is managed by a function that has been mapped to a
    specific modem state. For example, the method that handles the case where
    the modem is in the ENABLED state would look like:

        def _HandleEnabledState(self):
            # Do stuff.

    The correct method will be dynamically located and executed by the step
    function according to the dictionary returned by the subclass'
    implementation of StateMachine._GetModemStateFunctionMap.

    """
    def __init__(self, modem):
        self._modem = modem
        self._started = False
        self._done = False
        self._trans_func_map = self._GetModemStateFunctionMap()

    @property
    def cancelled(self):
        """
        @return True, if the state machine has been cancelled or has
                transitioned to a terminal state. False, otherwise.

        """
        return self._done

    def Cancel(self):
        """
        Tells the state machine to stop transitioning to further states.

        """
        self._done = True

    def Step(self):
        """
        Executes the next corresponding state transition based on the modem
        state.

        """
        logging.info('StateMachine: Step')
        if self._done:
            logging.info('StateMachine: Terminating.')
            return

        if not self._started:
            if not self._ShouldStartStateMachine():
                logging.info('StateMachine cannot start.')
                return
            self._started = True

        state = self._GetCurrentState()
        func = self._trans_func_map.get(state, self._GetDefaultHandler())
        if func and func(self):
            self._ScheduleNextStep()
        else:
            self._done = True

    def _ScheduleNextStep(self):
        """
        Schedules the next state transition to execute on the idle loop.
        subclasses can override this method to implement custom logic, such as
        delays.

        """
        gobject.idle_add(StateMachine.Step, self)

    def _GetDefaultHandler(self):
        """
        Returns the function to handle a modem state, for which the value
        returned by StateMachine._GetModemStateFunctionMap is None. The
        returned function's signature must match:

            StateMachine -> Boolean

        This function by default returns None. If no function exists to handle
        a modem state, the default behavior is to terminate the state machine.

        """
        return None

    def _GetModemStateFunctionMap(self):
        """
        Returns a mapping from modem states to corresponding transition
        functions to execute. The returned function's signature must match:

            StateMachine -> Boolean

        The first argument to the function is a state machine, which will
        typically be passed a value of |self|. The return value, if True,
        indicates that the state machine should keep executing further state
        transitions. A return value of False indicates that the state machine
        will transition to a terminal state.

        This method must be implemented by a subclass. Subclasses can further
        override this method to provide custom functionality.

        """
        raise NotImplementedError()

    def _ShouldStartStateMachine(self):
        """
        This method will be called when the state machine is in a starting
        state. This method should return True, if the state machine can
        successfully begin its state transitions, False if it should not
        proceed. This method can also raise an exception in the failure case.

        In the success case, this method should also execute any necessary
        initialization steps.

        This method must be implemented by a subclass. Subclasses can
        further override this method to provide custom functionality.

        """
        raise NotImplementedError()

    def _GetCurrentState(self):
        """
        Get the current state of the state machine.

        This method is called to get the current state of the machine when
        deciding what the next transition should be.
        By default, the state machines are tied to the modem state, and this
        function simply returns the modem state.

        Subclasses can override this function to use custom states in the state
        machine.

        @returns The modem state.
        """
        return self._modem.Get(mm1.I_MODEM, 'State')
