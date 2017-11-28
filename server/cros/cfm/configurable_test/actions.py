"""
This module contains the actions that a configurable CFM test can execute.
"""
import abc
import logging
import random
import re
import sys

class Action(object):
    """
    Abstract base class for all actions.
    """
    __metaclass__ = abc.ABCMeta

    def __repr__(self):
        return self.__class__.__name__

    def execute(self, context):
        """
        Executes the action.

        @param context ActionContext instance providing dependencies to the
                action.
        """
        logging.info('Executing action "%s"', self)
        self.do_execute(context)
        logging.info('Done executing action "%s"', self)

    @abc.abstractmethod
    def do_execute(self, context):
        """
        Performs the actual execution.

        Subclasses must override this method.

        @param context ActionContext instance providing dependencies to the
                action.
        """
        pass

class MuteMicrophone(Action):
    """
    Mutes the microphone in a call.
    """
    def do_execute(self, context):
        context.cfm_facade.mute_mic()

class UnmuteMicrophone(Action):
    """
    Unmutes the microphone in a call.
    """
    def do_execute(self, context):
        context.cfm_facade.unmute_mic()

class JoinMeeting(Action):
    """
    Joins a meeting.
    """
    def __init__(self, meeting_code):
        """
        Initializes.

        @param meeting_code The meeting code for the meeting to join.
        """
        super(JoinMeeting, self).__init__()
        self.meeting_code = meeting_code

    def __repr__(self):
        return 'JoinMeeting "%s"' % self.meeting_code

    def do_execute(self, context):
        context.cfm_facade.join_meeting_session(self.meeting_code)

class CreateMeeting(Action):
    """
    Creates a new meeting from the landing page.
    """
    def do_execute(self, context):
        context.cfm_facade.start_meeting_session()

class LeaveMeeting(Action):
    """
    Leaves the current meeting.
    """
    def do_execute(self, context):
        context.cfm_facade.end_meeting_session()

class RebootDut(Action):
    """
    Reboots the DUT.
    """
    def __init__(self, restart_chrome_for_cfm=False):
        """Initializes.

        To enable the cfm_facade to interact with the CFM, Chrome needs an extra
        restart. Setting restart_chrome_for_cfm toggles this extra restart.

        @param restart_chrome_for_cfm If True, restarts chrome to enable
                the cfm_facade and waits for the telemetry commands to become
                available. If false, does not do an extra restart of Chrome.
        """
        self._restart_chrome_for_cfm = restart_chrome_for_cfm

    def do_execute(self, context):
        context.host.reboot()
        if self._restart_chrome_for_cfm:
            context.cfm_facade.restart_chrome_for_cfm()
            context.cfm_facade.wait_for_meetings_telemetry_commands()

class RepeatTimes(Action):
    """
    Repeats a scenario a number of times.
    """
    def __init__(self, times, scenario):
        """
        Initializes.

        @param times The number of times to repeat the scenario.
        @param scenario The scenario to repeat.
        """
        super(RepeatTimes, self).__init__()
        self.times = times
        self.scenario = scenario

    def __str__(self):
        return 'Repeat[scenario=%s, times=%s]' % (self.scenario, self.times)

    def do_execute(self, context):
        for _ in xrange(self.times):
            self.scenario.execute(context)

class AssertFileDoesNotContain(Action):
    """
    Asserts that a file on the DUT does not contain specified regexes.
    """
    def __init__(self, path, forbidden_regex_list):
        """
        Initializes.

        @param path The file path on the DUT to check.
        @param forbidden_regex_list a list with regular expressions that should
                not appear in the file.
        """
        super(AssertFileDoesNotContain, self).__init__()
        self.path = path
        self.forbidden_regex_list = forbidden_regex_list

    def __repr__(self):
        return ('AssertFileDoesNotContain[path=%s, forbidden_regex_list=%s'
                % (self.path, self.forbidden_regex_list))

    def do_execute(self, context):
        contents = context.file_contents_collector.collect_file_contents(
                self.path)
        for forbidden_regex in self.forbidden_regex_list:
            match = re.search(forbidden_regex, contents)
            if match:
                raise AssertionError(
                        'Regex "%s" matched "%s" in "%s"'
                        % (forbidden_regex, match.group(), self.path))

class AssertUsbDevices(Action):
    """
    Asserts that USB devices with a given spec matches a predicate.
    """
    def __init__(
            self,
            usb_device_spec,
            predicate=lambda usb_device_list: len(usb_device_list) == 1):
        """
        Initializes with a spec to assert and a predicate.

        @param usb_device_spec an UsbDeviceSpec for the device to check.
        @param predicate A function that accepts a list of UsbDevices
                and returns true if the list is as expected or false otherwise.
                If the method returns false an AssertionError is thrown.
                The default predicate checks that there is exactly one item
                in the list.
        """
        super(AssertUsbDevices, self).__init__()
        self._usb_device_spec = usb_device_spec
        self._predicate = predicate

    def do_execute(self, context):
        usb_devices = context.usb_device_collector.get_devices_by_spec(
                self._usb_device_spec)
        if not self._predicate(usb_devices):
            raise AssertionError(
                    'Assertion failed for usb device spec %s. '
                    'Usb devices were: %s'
                    % (self._usb_device_spec, usb_devices))

    def __str__(self):
        return 'AssertUsbDevices for spec %s' % self._usb_device_spec

class SelectScenarioAtRandom(Action):
    """
    Executes a randomly selected scenario a number of times.

    Note that there is no validation performed - you have to take care
    so that it makes sense to execute the supplied scenarios in any order
    any number of times.
    """
    def __init__(
            self,
            scenarios,
            run_times,
            random_seed=random.randint(0, sys.maxsize)):
        """
        Initializes.

        @param scenarios An iterable with scenarios to choose from.
        @param run_times The number of scenarios to run. I.e. the number of
            times a random scenario is selected.
        @param random_seed The seed to use for the random generator. Providing
            the same seed as an earlier run will execute the scenarios in the
            same order. Optional, by default a random seed is used.
        """
        super(SelectScenarioAtRandom, self).__init__()
        self._scenarios = scenarios
        self._run_times = run_times
        self._random_seed = random_seed
        self._random = random.Random(random_seed)

    def do_execute(self, context):
        for _ in xrange(self._run_times):
            self._random.choice(self._scenarios).execute(context)

    def __repr__(self):
        return ('SelectScenarioAtRandom [seed=%s, run_times=%s, scenarios=%s]'
                % (self._random_seed, self._run_times, self._scenarios))

