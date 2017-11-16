"""
This module contains the actions that a configurable CFM test can execute.
"""
import abc

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
        self.times = times
        self.scenario = scenario

    def __str__(self):
        return 'RepeatTimes %s %s times' % (self.scenario, self.times)

    def execute(self, context):
        for _ in xrange(self.times):
            self.scenario.execute(context)

