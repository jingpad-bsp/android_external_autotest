# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""RDB utilities.

Do not import rdb or autotest modules here to avoid cyclic dependencies.
"""
import itertools


class RDBException(Exception):
    """Generic RDB exception."""

    def wire_format(self, **kwargs):
        """Convert the exception to a format better suited to an rpc response.
        """
        return str(self)


# Custom iterators: Used by the rdb to lazily convert the iteration of a
# queryset to a database query and return an appropriately formatted response.
class RememberingIterator(object):
    """An iterator capable of reproducing all values in the input generator.
    """

    #pylint: disable-msg=C0111
    def __init__(self, gen):
        self.current, self.history = itertools.tee(gen)
        self.items = []


    def __iter__(self):
        return self


    def next(self):
        return self.current.next()


    def get_all_items(self):
        """Get all the items in the generator this object was created with.

        @return: A list of items.
        """
        if not self.items:
            self.items = list(self.history)
        return self.items


class LabelIterator(RememberingIterator):
    """A RememberingIterator for labels.

    Within the rdb any label/dependency comparisons are performed based on label
    ids. However, the host object returned needs to contain label names instead.
    This class returns the label id when iterated over, but a list of all label
    names when accessed through get_all_items.
    """


    def next(self):
        return super(LabelIterator, self).next().id


    def get_all_items(self):
        """Get all label names of the labels in the input generator.

        @return: A list of label names.
        """
        return [label.name
                for label in super(LabelIterator, self).get_all_items()]

