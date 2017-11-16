class ActionContext(object):
    """
    Provides the dependencies actions might need to execute.
    """
    def __init__(self, cfm_facade=None):
        """
        Initializes.

        @param cfm_facade CFM facade to use, an instance of
                CFMFacadeRemoteAdapter.
        """
        self.cfm_facade = cfm_facade
