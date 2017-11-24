import mock
import unittest

from autotest_lib.server.cros.cfm.configurable_test import actions
from autotest_lib.server.cros.cfm.configurable_test import action_context

# Test, disable missing-docstring
# pylint: disable=missing-docstring
class TestActions(unittest.TestCase):
    """
    Tests for the available actions for configurable CFM tests to run.
    """

    def setUp(self):
        self.host_mock = mock.MagicMock()
        self.cfm_facade_mock = mock.MagicMock()

    def test_assert_file_does_not_contain_no_match(self):
        action = actions.AssertFileDoesNotContain('/foo', ['EE', 'WW'])
        context = action_context.ActionContext(
                file_contents_collector=FakeCollector('abc\ndef'))
        action.execute(context)

    def test_assert_file_does_not_contain_match(self):
        action = actions.AssertFileDoesNotContain('/foo', ['EE', 'WW'])
        context = action_context.ActionContext(
                file_contents_collector=FakeCollector('abc\naWWd'))
        self.assertRaises(AssertionError, lambda: action.execute(context))

    def test_assert_file_does_not_contain_regex_match(self):
        action = actions.AssertFileDoesNotContain('/foo', ['EE', 'W{3}Q+'])
        context = action_context.ActionContext(
                file_contents_collector=FakeCollector('abc\naWWWQQd'))
        self.assertRaises(AssertionError, lambda: action.execute(context))

    def test_reboot_dut_no_restart(self):
        action = actions.RebootDut()
        context = action_context.ActionContext(
                cfm_facade=self.cfm_facade_mock,
                host=self.host_mock)
        action.execute(context)
        self.host_mock.reboot.assert_called_once_with()
        self.assertFalse(self.cfm_facade_mock.method_calls)

    def test_reboot_dut_with_restart(self):
        action = actions.RebootDut(restart_chrome_for_cfm=True)
        context = action_context.ActionContext(
                cfm_facade=self.cfm_facade_mock,
                host=self.host_mock)
        action.execute(context)
        self.host_mock.reboot.assert_called_once_with()
        (self.cfm_facade_mock.restart_chrome_for_cfm
                .assert_called_once_with())
        (self.cfm_facade_mock.wait_for_meetings_telemetry_commands
                .assert_called_once_with())


class FakeCollector(object):
    def __init__(self, contents):
        self.contents = contents

    def collect_file_contents(self, path):
        return self.contents

