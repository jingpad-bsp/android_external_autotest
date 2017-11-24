class CrasInputNode(object):
    """Class representing an input node from ChromeOS Audio Server data.

    An input node is a node that can pick up audio, e.g. a microphone jack.
    """

    def __init__(self, node_id, name, gain, node_type):
        self.node_id = node_id
        self.name = name
        self.gain = gain
        self.node_type = node_type
