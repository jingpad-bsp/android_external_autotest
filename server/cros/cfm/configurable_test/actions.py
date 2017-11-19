"""
This module contains the actions that a configurable CFM test can execute.
"""
import abc
import re

class Action(object):
    """
    Abstract base class for all actions.
    """
    __metaclass__ = abc.ABCMeta

    def __str__(self):
        return self.__class__.__name__

    @abc.abstractmethod
    def execute(self, context):
        """
        Executes the action.

        Subclasses must override this method.

        @param context ActionContext instance provinding dependencies to the
                action.
        """
        pass

class MuteMicrophone(Action):
    """
    Mutes the microphone in a call.
    """
    def execute(self, context):
        context.cfm_facade.mute_mic()

class UnmuteMicrophone(Action):
    """
    Unmutes the microphone in a call.
    """
    def execute(self, context):
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

    def __str__(self):
        return 'JoinMeeting "%s"' % self.meeting_code

    def execute(self, context):
        context.cfm_facade.join_meeting_session(self.meeting_code)

class CreateMeeting(Action):
    """
    Creates a new meeting from the landing page.
    """
    def execute(self, context):
        context.cfm_facade.start_meeting_session()

class LeaveMeeting(Action):
    """
    Leaves the current meeting.
    """
    def execute(self, context):
        context.cfm_facade.end_meeting_session()

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
        return 'Repeat %s %s times' % (self.scenario, self.times)

    def execute(self, context):
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

    def __str__(self):
        return 'Assert %s does not contain %s' % (self.path,
                                                  self.forbidden_regex_list)

    def execute(self, context):
        contents = context.file_contents_collector.collect_file_contents(
                self.path)
        for forbidden_regex in self.forbidden_regex_list:
            match = re.search(forbidden_regex, contents)
            if match:
                raise AssertionError(
                        'Regex "%s" matched "%s" in "%s"'
                        % (forbidden_regex, match.group(), self.path))

