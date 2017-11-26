class CrasOutputNode(object):
    """Class representing an output node from ChromeOS Audio Server data.

    An output node is a node that can play out audio, e.g. a headphone jack.
    """

    def __init__(self, node_id, node_type, name):
        self.node_id = node_id
        self.node_type = node_type
        self.name = name
