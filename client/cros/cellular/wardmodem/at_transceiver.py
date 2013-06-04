# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging

import at_channel
import task_loop

MODEM_RESPONSE_TIMEOUT_MILLISECONDS = 30000

class ATTransceiverMode(object):
    """
    Enum to specify what mode the ATTransceiver is operating in.

    There are three modes. These modes determine how the commands to/from
    the modemmanager are routed.
        WARDMODEM:  modemmanager interacts with wardmodem alone.
        SPLIT_VERIFY: modemmanager commands are sent to both the wardmodem
                and the physical modem on the device. Responses from
                wardmodem are verified against responses from the physical
                modem. In case of a mismatch, wardmodem's response is
                chosen, and a warning is issued.
        PASS_THROUGH: modemmanager commands are routed to/from the physical
                modem. Frankly, wardmodem isn't running in this mode.

    """
    WARDMODEM = 0
    SPLIT_VERIFY = 1
    PASS_THROUGH = 2

    MODE_NAME = {
            WARDMODEM: 'WARDMODEM',
            SPLIT_VERIFY: 'SPLIT_VERIFY',
            PASS_THROUGH: 'PASS_THROUGH'
    }


    @classmethod
    def to_string(cls, value):
        """
        A class method to obtain string representation of the enum values.

        @param value: the enum value to stringify.
        """
        return "%s.%s" % (cls.__name__, cls.MODE_NAME[value])


class ATTransceiver(object):
    """
    A world facing multiplexer class that orchestrates the communication between
    modem manager, the physical modem, and wardmodem back-end.

    """

    def __init__(self, mm_at_port, modem_at_port=None):
        """
        @param mm_at_port: File descriptor for AT port used by modem manager.
                Can not be None.

        @param modem_at_port: File descriptor for AT port used by the modem. May
                be None, but that forces ATTransceiverMode.WARDMODEM. Default:
                None.

        """
        super(ATTransceiver, self).__init__()
        assert mm_at_port is not None

        self._logger = logging.getLogger(__name__)
        self._task_loop = task_loop.get_instance()
        self._mode = ATTransceiverMode.WARDMODEM
        # The time we wait for any particular response from physical modem.
        self._modem_response_timeout_milliseconds = (
                MODEM_RESPONSE_TIMEOUT_MILLISECONDS)
        # We keep a queue of responses from the wardmodem and physical modem,
        # so that we can verify they match.
        self._cached_modem_responses = collections.deque()
        self._cached_wardmodem_responses = collections.deque()
        # When a wardmodem response has been received but the corresponding
        # physical modem response hasn't arrived, we post a task to wait for the
        # response.
        self._modem_response_wait_task = None

        if modem_at_port is not None:
            self._modem_channel = at_channel.ATChannel(
                    self._process_modem_at_command,
                    modem_at_port,
                    'modem_primary_channel')
        else:
            self._modem_channel = None

        self._mm_channel = at_channel.ATChannel(self._process_mm_at_command,
                                                mm_at_port,
                                                'mm_primary_channel')


    # Verification failure reasons
    VERIFICATION_FAILED_MISMATCH = 1
    VERIFICATION_FAILED_TIME_OUT = 2


    @property
    def mode(self):
        """
        ATTranscieverMode value. Determines how commands are routed.

        @see ATTransceiverMode

        """
        return self._mode


    @mode.setter
    def mode(self, value):
        """
        Set mode.

        @param value: The value to set. Type: ATTransceiverMode.

        """
        if value != ATTransceiverMode.WARDMODEM and self._modem_channel is None:
            self._logger.warning(
                    'Can not switch to %s mode. No modem port provided.',
                    ATTransceiverMode.to_string(value))
            return
        self._logger.info('Set mode to %s',
                          ATTransceiverMode.to_string(value))
        self._mode = value


    @property
    def at_terminator(self):
        """
        The string used to terminate AT commands sent / received on the channel.

        Default value: '\r\n'
        """
        return self._mm_channel.at_terminator

    @at_terminator.setter
    def at_terminator(self, value):
        """
        Set the string to use to terminate AT commands.

        This can vary by the modem being used.

        @param value: The string terminator.

        """
        assert self._mm_channel
        self._mm_channel.at_terminator = value
        if self._modem_channel:
            self._modem_channel.at_terminator = value


    def process_wardmodem_response(self, response):
        """
        TODO(pprabhu)

        @param response: wardmodem response to be translated to AT response to
                the modem manager.

        """
        raise NotImplementedError()

    # ##########################################################################
    # Callbacks -- These are the functions that process events from the
    # ATChannel or the TaskLoop. These functions are either
    #   (1) set as callbacks in the ATChannel, or
    #   (2) called internally to process the AT command to/from the TaskLoop.

    def _process_modem_at_command(self, command):
        """
        Callback called by the physical modem channel when an AT response is
        received.

        @param command: AT command sent by the physical modem.

        """
        assert self.mode != ATTransceiverMode.WARDMODEM
        self._logger.debug('Command {modem ==> []}: |%s|', command)
        if self.mode == ATTransceiverMode.PASS_THROUGH:
            self._logger.debug('Command {[] ==> mm}: |%s|' , command)
            self._mm_channel.send(command)
        else:
            self._cached_modem_responses.append(command)
            self._verify_and_send_mm_commands()


    def _process_mm_at_command(self, command):
        """
        Callback called by the modem manager channel when an AT command is
        received.

        @param command: AT command sent by modem manager.

        """
        self._logger.debug('Command {mm ==> []}: |%s|', command)
        if(self.mode == ATTransceiverMode.PASS_THROUGH or
           self.mode == ATTransceiverMode.SPLIT_VERIFY):
            self._logger.debug('Command {[] ==> modem}: |%s|', command)
            self._modem_channel.send(command)
        if(self.mode == ATTransceiverMode.WARDMODEM or
           self.mode == ATTransceiverMode.SPLIT_VERIFY):
            self._logger.debug('Command {[] ==> wardmodem}: |%s|', command)
            self._post_wardmodem_request(command)


    def _process_wardmodem_at_command(self, command):
        """
        Function called to process an AT command response of wardmodem.

        This function is called after the response from the task loop has been
        converted to an AT command.

        @param command: The AT command response of wardmodem.

        """
        assert self.mode != ATTransceiverMode.PASS_THROUGH
        self._logger.debug('Command {wardmodem ==> []: |%s|', command)
        if self.mode == ATTransceiverMode.WARDMODEM:
            self._logger.debug('Command {[] ==> mm}: |%s|', command)
            self._mm_channel.send(command)
        else:
            self._cached_wardmodem_responses.append(command)
            self._verify_and_send_mm_commands()


    def _post_wardmodem_request(self, request):
        """
        TODO(pprabhu)

        @param request: wardmodem request posted to satisfy a modemmanager AT
                command.

        """
        raise NotImplementedError()

    # ##########################################################################
    # Helper functions

    def _verify_and_send_mm_commands(self):
        """
        While there are corresponding responses from wardmodem and physical
        modem, verify that they match and respond to modem manager.

        """
        if not self._cached_wardmodem_responses:
            return
        elif not self._cached_modem_responses:
            if self._modem_response_wait_task is not None:
                return
            self._modem_response_wait_task = (
                    self._task_loop.post_task_after_delay(
                            self._modem_response_timed_out,
                            self._modem_response_timeout_milliseconds))
        else:
            if self._modem_response_wait_task is not None:
                self._task_loop.cancel_posted_task(
                        self._modem_response_wait_task)
                self._modem_response_wait_task = None
            self._verify_and_send_mm_command(
                    self._cached_modem_responses.popleft(),
                    self._cached_wardmodem_responses.popleft())
            self._verify_and_send_mm_commands()


    def _verify_and_send_mm_command(self, modem_response, wardmodem_response):
        """
        Verify that the two AT commands match and respond to modem manager.

        @param modem_response: AT command response of the physical modem.

        @param wardmodem_response: AT command response of wardmodem.

        """
        # TODO(pprabhu) This can not handle unsolicited commands yet.
        # Unsolicited commands from either of the modems will push the lists out
        # of sync.
        if wardmodem_response != modem_response:
            self._logger.warning('Response verification failed.')
            self._logger.warning('modem response: |%s|', modem_response)
            self._logger.warning('wardmodem response: |%s|', wardmodem_response)
            self._logger.warning('wardmodem response takes precedence.')
            self._report_verification_failure(
                    self.VERIFICATION_FAILED_MISMATCH,
                    modem_response,
                    wardmodem_response)
        self._logger.debug('Command {[] ==> mm}: |%s|' , wardmodem_response)
        self._mm_channel.send(wardmodem_response)


    def _modem_response_timed_out(self):
        """
        Callback called when we time out waiting for physical modem response for
        some wardmodem response. Can't do much -- log physical modem failure and
        forward wardmodem response anyway.

        """
        assert (not self._cached_modem_responses and
                self._cached_wardmodem_responses)
        wardmodem_response = self._cached_wardmodem_responses.popleft()
        self._logger.warning('modem response timed out. '
                             'Forwarding wardmodem response |%s| anyway.',
                             wardmodem_response)
        self._logger.debug('Command {[] ==> mm}: |%s|' , wardmodem_response)
        self._report_verification_failure(
                self.VERIFICATION_FAILED_TIME_OUT,
                None,
                wardmodem_response)
        self._mm_channel.send(wardmodem_response)
        self._modem_response_wait_task = None
        self._verify_and_send_mm_commands()


    def _report_verification_failure(self, failure, modem_response,
                                     wardmodem_response):
        """
        Failure to verify the wardmodem response will call this non-public
        method.

        At present, it is only used by unittests to detect failure.

        @param failure: The cause of failure. Must be one of
                VERIFICATION_FAILED_MISMATCH or VERIFICATION_FAILED_TIME_OUT.

        @param modem_response: The received modem response (if any).

        @param wardmodem_response: The received wardmodem response.

        """
        pass


