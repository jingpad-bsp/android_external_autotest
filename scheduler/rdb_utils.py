# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""RDB utilities.

Do not import rdb or autotest modules here to avoid cyclic dependencies.
"""

RDB_STATS_KEY = 'rdb'

class RDBException(Exception):
    """Generic RDB exception."""

    def wire_format(self, **kwargs):
        """Convert the exception to a format better suited to an rpc response.
        """
        return str(self)


class CacheMiss(RDBException):
    """Generic exception raised for a cache miss in the rdb."""
    pass


class LabelIterator(object):
    """An Iterator for labels.

    Within the rdb any label/dependency comparisons are performed based on label
    ids. However, the host object returned needs to contain label names instead.
    This class returns label ids for iteration, but a list of all label names
    when accessed through get_label_names.
    """

    def __init__(self, labels):
        self.labels = labels


    def __iter__(self):
        return iter(label.id for label in self.labels)


    def get_label_names(self):
        """Get all label names of the labels associated with this class.

        @return: A list of label names.
        """
        return [label.name for label in self.labels]

