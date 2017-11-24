from autotest_lib.client.common_lib.cros.cfm import cras_input_node
from autotest_lib.client.common_lib.cros.cfm import cras_output_node

class CrasNodeCollector(object):
    """Utility class for obtaining node data from cras_test_client."""

    OUTPUT_NODE_HEADERS = ['Stable Id', 'ID', 'Vol', 'Plugged', 'L/R swapped',
                           'Time Hotword', 'Type', 'Name']
    INPUT_NODE_HEADERS = ['Stable Id', 'ID', 'Gain', 'Plugged', 'L/Rswapped',
                          'Time Hotword', 'Type', 'Name']

    def __init__(self, host):
        """
        Constructor
        @param host the device under test (CrOS).
        """
        self._host = host

    def _replace_multiple_whitespace_with_one(self, string):
        """
        Replace multiple sequential whitespaces with a single whitespace.
        @returns a string
        """
        return ' '.join(string.split())

    def _construct_columns(self, columns_str):
        """
        Constructs a list of strings from a single string.

        @param columns_str A whitespace separated list of values.
        @returns a list with strings.
        """
        # 1) Replace multiple whitespaces with one
        # 2) Split on whitespace, create 8 columns
        columns_str = self._replace_multiple_whitespace_with_one(columns_str)
        return columns_str.split(None, 7)

    def _collect_output_node_cras_data(self):
        """
        Collects output nodes data using cras_test_client.

        @returns a list of dictionaries where keys are in OUTPUT_NODE_HEADERS
        """
        # It's a bit hacky to use awk; we should probably do the parsing
        # in Python instead using textfsm or some other lib.
        cmd = ("cras_test_client --dump_server_info"
               "| awk '/Output Nodes:/,/Input Devices:/'")
        lines = self._host.run_output(cmd).split('\n')
        # Ignore the first two lines ("Output Nodes:" and headers) and the
        # last line ("Input Devices:")
        lines = lines[2:-1]
        rows = [self._construct_columns(line) for line in lines]
        return [dict(zip(self.OUTPUT_NODE_HEADERS, row)) for row in rows]

    def _collect_input_node_cras_data(self):
        """
        Collects input nodes data using cras_test_client.

        @returns a list of dictionaries where keys are in INPUT_NODE_HEADERS
        """
        cmd = ("cras_test_client --dump_server_info "
              " | awk '/Input Nodes:/,/Attached clients:/'")
        lines = self._host.run_output(cmd).split('\n')
        # Ignore the first two lines ("Input Nodes:" and headers) and the
        # last line ("Attached clients:")
        lines = lines[2:-1]
        rows = [self._construct_columns(line) for line in lines]
        return [dict(zip(self.INPUT_NODE_HEADERS, row)) for row in rows]

    def _create_input_node(self, data):
        return cras_input_node.CrasInputNode(
            node_id=data['ID'],
            name=data['Name'],
            gain=data['Gain'],
            node_type=data['Type'])

    def _create_output_node(self, data):
        return cras_output_node.CrasOutputNode(
            node_id=data['ID'],
            node_type=data['Type'],
            name=data['Name'])

    def get_input_nodes(self):
        crasdata = self._collect_input_node_cras_data()
        return [self._create_input_node(d) for d in crasdata]

    def get_output_nodes(self):
        crasdata = self._collect_output_node_cras_data()
        return [self._create_output_node(d) for d in crasdata]
