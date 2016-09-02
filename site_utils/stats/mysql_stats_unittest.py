"""Tests for mysql_stats."""

import common

import mock
import unittest

import mysql_stats


class MysqlStatsTest(unittest.TestCase):
    """Unittest for mysql_stats."""

    def testQueryAndEmit(self):
        """Test for QueryAndEmit."""
        cursor = mock.Mock()
        cursor.execute = mock.Mock(return_value=0)

        # This shouldn't raise an exception.
        mysql_stats.QueryAndEmit(cursor)


if __name__ == '__main__':
    unittest.main()
