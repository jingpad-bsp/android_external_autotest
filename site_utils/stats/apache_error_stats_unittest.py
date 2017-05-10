"""Tests for mysql_stats."""

import os
import unittest

import common

import apache_error_stats


class ApacheErrorTest(unittest.TestCase):
    """Unittest for the apache error log regexp."""

    def testNonMatchingLine(self):
        """Test for log lines which don't match the expected format.."""
        lines = [
          '[] [] [] blank components',
          '[] [:error] [] no "pid" section',
          '[] [:error] [pid 1234] no timestamp',
          '[hello world] [:] [pid 1234] no log level',
          '[hello] [:error] [pid 42]     too far indented.'
        ]
        for line in lines:
          self.assertEqual(
              None, apache_error_stats.ERROR_LOG_MATCHER.match(line))

    def testMatchingLines(self):
        """Test for lines that are expected to match the format."""
        match = apache_error_stats.ERROR_LOG_MATCHER.match(
            "[foo] [:bar] [pid 123] WARNING")
        self.assertEqual('bar', match.group('log_level'))
        self.assertEqual(None, match.group('mod_wsgi'))

        match = apache_error_stats.ERROR_LOG_MATCHER.match(
            "[foo] [:bar] [pid 123] mod_wsgi (pid=123)")
        self.assertEqual('bar', match.group('log_level'))
        self.assertEqual('od_wsgi', match.group('mod_wsgi'))

    def testExampleLog(self):
        """Try on some example lines from a real apache error log."""
        with open(os.path.join(os.path.dirname(__file__),
                               'apache_error_log_example.txt')) as fh:
          example_log = fh.readlines()
        matcher_output = [apache_error_stats.ERROR_LOG_MATCHER.match(line)
                          for line in example_log]
        matched = filter(bool, matcher_output)
        self.assertEqual(5, len(matched))

        self.assertEqual('error', matched[0].group('log_level'))
        self.assertEqual(None, matched[0].group('mod_wsgi'))

        self.assertEqual('warn', matched[1].group('log_level'))
        self.assertEqual('od_wsgi', matched[1].group('mod_wsgi'))

        self.assertEqual('error', matched[2].group('log_level'))
        self.assertEqual(None, matched[2].group('mod_wsgi'))

        self.assertEqual('error', matched[3].group('log_level'))
        self.assertEqual(None, matched[3].group('mod_wsgi'))

        self.assertEqual('error', matched[4].group('log_level'))
        self.assertEqual(None, matched[4].group('mod_wsgi'))


if __name__ == '__main__':
    unittest.main()
