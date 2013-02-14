#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A thread pool library that spreads work across processors.

By default python restricts itself to a single processor.  So even when
additional threads are created they still execute sequentially on one processor
due to python's Global Interpreter Lock.  To work around this limitation and
take advantage of multi-core and multi-processor computers this library spawns
additional python processes which execute on different processors.  Then each
of these processes create additional threads to attempt to fully parallelize the
work submitted to the pool.

To use this library instantiate an instance of MultiProcWorkPool and call
ExecuteWorkItems(work_items).
  Args:
    work_items: A list of objects with an Execute() method to call.

  Examples:

  class WorkClass(object):
    def __init__(self, val):
      self.val = val

    def Execute(self):
      self.val = self.val * self.val

    def ExecuteWithLogger(self, logger):
      self.val = self.val * self.val
      logger.info('val=%s', self.val)

  def SomeOtherFunction()
    # Build some objects to submit to work pool
    work_items = [WorkClass(i) for i in range(100)]

    # Submit objects to pool and get results
    mp_tp = tp.MultiProcWorkPool()
    work_items = mp_tp.ExecuteWorkItems(work_items)

    # Call again with a logger provided to the method
    work_items = mp_tp.ExecuteWorkItems(work_items, 'ExecuteWithLogger',
                                        provide_logger=True)


Callback responsibilities
  1 - Do not hang.  The thread executing the callback cannot detect or deal
      with a hung callback itself.  (The pool cannot use timers to deal with
      this situation because timers only fire on the main thread in a process
      and the hung work item is on a spawned thread.)
  2 - Only throw a CallbackError exception.  This is exception is handled.  If
      another exception is thrown it will go unhandled and terminate the thread
      executing this callback and prevent it from picking up more work from the
      queue.  A watchdog thread will eventually notice this and add more
      threads to the pool, but this is generally bad.
  3 - When CallbackError is thrown, expect that as the return from the callback.
      If you normally return a single int as a return code and sometimes throw
      this exception, your post processing may go wonky if you don't expect to
      see the exception message and stack trace as the return.


Help!  It is not working for me.  How do I troubleshoot?
  If things don't work narrow down the issue by constraining the pool in this
  order to help identify where the problem is.
    1 - Set proc count to 0:  This will prevent any processes from being
        created and the work will execute in the main calling process.  This
        mode will help distinguish between errors dealing with any work being
        submitted to the pool and errors from work completing on different
        processes.  Different processes do not share resources that your
        callback may expect them to.
    2 - One Proc One Thread: Make sure you work works when executed in the pool.
        Creating a single process will force the work to be done in a different
        process than the requesting process.
    2 - One Proc Multi Thread: Make sure threads don't cause issues.
    3 - Multi Proc One Thread: Make sure processes don't cause issues.
"""


__author__ = 'pauldean@google.com (Paul Pendlebury)'


import inspect
import logging
import multiprocessing as mp
import os
import Queue
import threading
import types


class Error(Exception):
  """Base exception for this module."""
  pass


class CallbackError(Error):
  """Only exception caught by the thread executing a user callback."""
  pass


# Time in seconds the stall check timer waits to check for missing threads.
DEFAULT_STALL_CHECK_INTERVAL = 5


# Default number of threads each worker processes should create.
DEFAULT_THREADS_PER_PROC = 8


# Time in seconds to wait for a process to complete it's portion of the work.
DEFAULT_PROCESS_TIMEOUT = 120


class ExecuteWorkItemsWorkerThread(threading.Thread):
  """Thread that runs work method on user items."""

  def __init__(self, input_queue, input_queue_lock, output_queue,
               output_queue_lock, method_name, logger=None):
    threading.Thread.__init__(self)
    self._input_queue = input_queue
    self._input_queue_lock = input_queue_lock
    self._output_queue = output_queue
    self._output_queue_lock = output_queue_lock
    self._method_name = method_name
    self._logger = logger

  def run(self):
    """Execute work in input_queue."""
    while True:
      try:
        self._input_queue_lock.acquire()
        work_obj = self._input_queue.get_nowait()
      except Queue.Empty:
        break
      finally:
        self._input_queue_lock.release()

      try:
        func = getattr(work_obj, self._method_name, None)
        if self._logger:
          func(self._logger)
        else:
          func()

        if self._output_queue:
          self._output_queue_lock.acquire()
          self._output_queue.put(work_obj)
          self._output_queue_lock.release()
      except CallbackError:
        pass
      finally:
        self._input_queue_lock.acquire()
        self._input_queue.task_done()
        self._input_queue_lock.release()


def ExecuteWorkItemsThreadInjectionCallback(input_queue, input_queue_lock,
                                            output_queue, output_queue_lock,
                                            method_name, max_threads, logger):
  """Timer callback.  Watchdog function that makes sure threads are working.

  This callback checks the number of active threads in the process and makes
  sure there are threads working on the queue.  Threads die when the callback
  throws an exception other than CallbackError.  So if 100 work items were
  submitted to this process, this process started 10 threads, and half way
  through the work 10 exceptions were thrown by callbacks, work would stall and
  the process would deadlock.  The 10 spawned threads would be terminated by
  unhandled exceptions and the work queue would still have half the work in it.

  This callback avoids this situation by checking every
  DEFAULT_STALL_CHECK_INTERVAL seconds that the number of active threads is
  still the target number, and if it is less it spawns new threads to continue
  working.

  @param input_queue: multiprocessing.manager.Queue() holding submitted work
                      items.
  @param input_queue_lock: lock for the input queue.
  @param output_queue: multiprocessing.manager.Queue() holding finished work
                       items.
  @param output_queue_lock: lock for the output queue.
  @param method_name: name of method to execute on each item.
  @param max_threads: maximum threads to start per worker process.
  @param logger: multiprocessing logger.
  """
  # We only care about the case when this timer fires and there is still work
  # in the queue.
  input_queue_lock.acquire()
  work_remaining = input_queue.qsize()
  input_queue_lock.release()

  if work_remaining > 0:
    # Enumerated threads include the thread this callback is running on as well
    # as the main thread of the process.  So to get the number of active worker
    # threads subtract 2 from the enumeration.
    active_worker_threads = len(threading.enumerate()) - 2

    # If we have fewer threads than we want, either some threads have died from
    # a problem in execution, or they've completed work.  But since the
    # work_queue is not empty no threads should have terminated from a lack of
    # work.  So lets restart some threads to avoid a stall in the work pool.
    if active_worker_threads < max_threads:
      required_threads = min(work_remaining,
                             max_threads - active_worker_threads)
      for i in range(required_threads):
        ExecuteWorkItemsWorkerThread(input_queue, input_queue_lock,
                                     output_queue, output_queue_lock,
                                     method_name, logger).start()

    # Setup a new timer now that this one has fired.
    threading.Timer(DEFAULT_STALL_CHECK_INTERVAL,
                    ExecuteWorkItemsThreadInjectionCallback,
                    (input_queue, input_queue_lock,
                     output_queue, output_queue_lock, method_name, max_threads,
                     logger)).start()


def ExecuteWorkItemsProcessCallback(input_queue, output_queue, method_name,
                                    max_threads, provide_logger=False,
                                    logger_init_callback=None,
                                    **logger_init_args):
  """Starts threads in a new process to perform requested work.

  @param input_queue: multiprocessing.manager.Queue() holding submitted work
                      items.
  @param output_queue: multiprocessing.manager.Queue() holding finished work
                       items.
  @param method_name: name of method to execute on each item.
  @param max_threads: maximum threads to start per worker process.
  @param provide_logger: if true provide a multiprocessing logger to the
                         callback.
  @param logger_init_callback: optional callback where user can setup logging.
  @param logger_init_args: optional arguments to logger_init_callback.
  """
  # Setup logging.
  logger = None
  if provide_logger:
    if logger_init_callback:
      logger = mp.get_logger()
      logger_init_callback(logger, **logger_init_args)
    else:
      logger = mp.log_to_stderr()
      logger.setLevel(logging.INFO)

  # The queue proxy objects from the multiprocessing manager are safe for
  # multiple processes to use simultaneously, but not safe for multiple threads
  # in those processes to access simultaneously.  So we need a lock per process
  # to synchronize access to the work queues.
  input_queue_lock = threading.Lock()
  output_queue_lock = None
  if output_queue:
    output_queue_lock = threading.Lock()

  assert max_threads > 0, 'Must request at least 1 thread per process.'
  thread_count = min(max_threads, input_queue.qsize())
  for i in range(thread_count):
    ExecuteWorkItemsWorkerThread(input_queue, input_queue_lock, output_queue,
                                 output_queue_lock, method_name, logger).start()

  # Start this processes watchdog thread.
  t = threading.Timer(DEFAULT_STALL_CHECK_INTERVAL,
                      ExecuteWorkItemsThreadInjectionCallback,
                      (input_queue, input_queue_lock,
                       output_queue, output_queue_lock, method_name,
                       max_threads, logger))
  t.start()

  # Wait for queue to drain.
  try:
    input_queue.join()
  except (KeyboardInterrupt, SystemExit):
    raise
  finally:
    t.cancel()


class MultiProcWorkPool(object):
  """Multi Processor Thread Pool implementation."""

  # TODO: Fix crosbug.com/38902 regarding procs=0 not being correctly
  # handled. Unit test for this module is disabled for now as a result
  # of bug.
  def __init__(self, procs=None, threads_per_proc=DEFAULT_THREADS_PER_PROC,
               max_threads=None):
    """Create an instance of MultiProcWorkPool.


    @param procs: Number of worker processes to spawn.  Default CPU count.  If
                 procs is 0 no processes will be created and the work will be
                 performed on the main process.
    @param threads_per_proc: Number of threads per processor to run.
    @param max_threads: Limit on total threads across all processors.
    """
    if procs is not None:
      assert procs >= 0, 'procs cannot be negative.'
      self._proc_count = procs
    else:
      self._proc_count = mp.cpu_count()

    assert threads_per_proc > 0, 'Must run at least 1 thread per process.'
    self._threads_per_proc = threads_per_proc

    # If max_threads does not divide evenly into proc_count the remainder will
    # be ignored and the work will be run on fewer threads rather than go over
    # the user supplied max_threads.  UNLESS the user asks for fewer threads
    # than proc_count, then we will use proc_count threads as each proc always
    # gets one worker thread.
    if max_threads:
      self._threads_per_proc = max(max_threads / max(self._proc_count, 1), 1)

    self._pool = mp.Pool(processes=self._proc_count)
    self._manager = mp.Manager()

  def ExecuteWorkItems(self, object_list, method_name='Execute',
                       return_objects=True, provide_logger=False,
                       logger_init_callback=None, **logger_init_args):
    """Distrubutes work on a list of objects across processes/threads.


    @param object_list: List of objects to call work method on.
    @param method_name: Name of method to execute on objects.
    @param return_objects: When true return a list of the objects after the work
                    has been executed.
    @param provide_logger: Pass a mp logger object to the execute method.
    @param logger_init_callback: Callback to be called once per process to allow
                           user to configure logging.  A bare logger will be
                           passed into the callback.  If logging is requested
                           and not callback is provided the default logging
                           will go to stderr.
    @param logger_init_args: Arguments to pass into logger_init_callback.

    @return: Either None or a list of objects when return_objects is True.
    """
    input_queue = self._manager.Queue()
    output_queue = None
    if return_objects:
      output_queue = self._manager.Queue()

    if logger_init_callback:
      assert callable(logger_init_callback), ('logger_init_callback is not a '
                                              'callable method.')
      argspec = inspect.getargspec(logger_init_callback)
      if logger_init_args:
        assert len(argspec.args) >= 2
      else:
        assert len(argspec.args) == 1

    assert object_list, 'Must supply work items.'
    assert type(object_list) is types.ListType, ('object_list parameter \"%s\" '
                                                 'is not  a List.'
                                                 % repr(object_list))
    first_obj = object_list[0]
    assert hasattr(first_obj, method_name), ('%s method missing from work '
                                             'items.' % method_name)
    func = getattr(first_obj, method_name)
    assert callable(func), '%s is not a callable method.' % method_name
    argspec = inspect.getargspec(func)
    if provide_logger:
      assert len(argspec.args) == 2, ('Logging was requested.  The parameters '
                                      'to %s should be [\'self\', \'logger\'] '
                                      'and not %s' % (method_name,
                                                      argspec.args))
    else:
      assert len(argspec.args) == 1, ('Logging was not requested.  The '
                                      'parameter to %s should be [\'self\'] '
                                      'and not %s' % (method_name,
                                                      argspec.args))
    obj_type = type(first_obj)
    for obj in object_list:
      assert obj_type == type(obj), 'Different types submitted.'
      input_queue.put(obj)

    # ZeroProc debug mode.  Don't spawn subprocesses to see if the problem
    # is related to interprocess communication/resource sharing.
    if self._proc_count == 0:
      ExecuteWorkItemsProcessCallback(input_queue, output_queue, method_name,
                                      self._threads_per_proc, provide_logger,
                                      logger_init_callback, logger_init_args)
    else:
      for i in range(self._proc_count):
        self._pool.apply_async(ExecuteWorkItemsProcessCallback,
                               (input_queue, output_queue, method_name,
                                self._threads_per_proc, provide_logger,
                                logger_init_callback), logger_init_args)
    # Wait for work to finish
    try:
      input_queue.join()
    except (KeyboardInterrupt, SystemExit):
      self._pool.terminate()
      raise

    # If the caller requested results take the mutated objects from the queue
    # and put them in a simple list to return.
    if output_queue:
      result_list = []
      while True:
        try:
          result_obj = output_queue.get_nowait()
          result_list.append(result_obj)
        except Queue.Empty:
          break
      return result_list


def ThreadDebugInfo():
  """Debug helper returning a string of the current process and thread."""

  return '[(pid:%s) %s : %s ]' % (os.getpid(), mp.current_process().name,
                                  threading.current_thread().name)
