#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for mp_thread_pool module."""

__author__ = 'pauldean@google.com (Paul Pendlebury)'


import logging
import unittest
import mp_thread_pool as tp


class WorkItemClass(object):
  """Class used for ExecuteWorkItems* tests.

  The test methods do easy to verify manipulations on the initial value of val.
  """

  def __init__(self, val):
    self.val = val
    self.new_val = None

  def Execute(self):
    """Set new_val to the square of val."""
    self.new_val = self.val * self.val

  def ExecuteWithLogger(self, logger=None):
    """Set val to new_val, and set new_val to twice new_val."""
    assert logger is not None, 'Logger missing in ExecuteWithLogger'
    self.val = self.new_val
    self.new_val = self.val + self.val


def SetLoggerFormat(logger):
  """Default logger formatting method."""
  logger.setLevel(logging.WARNING)
  stream_handler = logging.StreamHandler()
  stream_handler.setLevel(logging.WARNING)
  format_str = '%(asctime)s - %(levelname)s - %(message)s'
  stream_handler.setFormatter(logging.Formatter(format_str))
  logger.addHandler(stream_handler)


class MultiProcWorkPoolTest(unittest.TestCase):

  def ExecuteWorkItems(self, work_pool=None, iterations=100, use_logger=False):
    """Verify Execute and ExecuteWithLogger methods."""

    mp_tp = work_pool
    if not mp_tp:
      mp_tp = tp.MultiProcWorkPool()

    work_items = []
    for i in range(iterations):
      work_items.append(WorkItemClass(i))

    work_items = mp_tp.ExecuteWorkItems(work_items)
    for i in range(iterations):
      self.assertTrue(work_items[i].val * work_items[i].val ==
                      work_items[i].new_val)

    if use_logger:
      work_items = mp_tp.ExecuteWorkItems(work_items, 'ExecuteWithLogger',
                                          provide_logger=True,
                                          logger_init_callback=SetLoggerFormat)
      for i in range(iterations):
        self.assertTrue(work_items[i].val + work_items[i].val ==
                        work_items[i].new_val)

  def test01SingleExecution(self):
    """01 - Verify a single item can be submitted to the pool."""
    self.ExecuteWorkItems(iterations=1)

  def test02SingleExecution(self):
    """02 - Verify a single item can be submitted to the pool with a logger."""
    self.ExecuteWorkItems(iterations=1, use_logger=True)

  def test03SingleProcMultiThread(self):
    """03 - Verify work completes when using only 1 process."""
    mp_tp = tp.MultiProcWorkPool(procs=0)
    self.ExecuteWorkItems(mp_tp)

  def test04SingleProcMultiThread(self):
    """04 - Verify work completes when using only 1 process with a logger."""
    mp_tp = tp.MultiProcWorkPool(procs=0)
    self.ExecuteWorkItems(mp_tp, use_logger=True)

  def test05MultiProcSingleThread(self):
    """05 - Verify work completes using only 1 thread per proc."""
    mp_tp = tp.MultiProcWorkPool(threads_per_proc=1)
    self.ExecuteWorkItems(mp_tp)

  def test06MultiProcSingleThread(self):
    """06 - Verify work completes using only 1 thread per proc with a logger."""
    mp_tp = tp.MultiProcWorkPool(threads_per_proc=1)
    self.ExecuteWorkItems(mp_tp)

  def test07SingleProcSingleThread(self):
    """07 - Verify using only 1 process and 1 thread."""
    mp_tp = tp.MultiProcWorkPool(procs=0, threads_per_proc=1)
    self.ExecuteWorkItems(mp_tp)

  def test08SingleProcSingleThread(self):
    """08 - Verify using only 1 process and 1 thread with a logger."""
    mp_tp = tp.MultiProcWorkPool(procs=0, threads_per_proc=1)
    self.ExecuteWorkItems(mp_tp)

  def test09MultipleExecuteSamePool(self):
    """09 - Verify the same mp_tp object can perform repeated executions."""
    for i in range(10):
      self.ExecuteWorkItems(iterations=1000)

  def test10MultipleExecuteSamePoolWithLogger(self):
    """10 - Verify logger is provided to callbacks on all processes/threads."""
    for i in range(10):
      self.ExecuteWorkItems(iterations=100, use_logger=True)


def main():
  suite = unittest.TestLoader().loadTestsFromTestCase(MultiProcWorkPoolTest)
  alltests = unittest.TestSuite([suite])
  unittest.TextTestRunner(verbosity=2).run(alltests)


if __name__ == '__main__':
  main()
