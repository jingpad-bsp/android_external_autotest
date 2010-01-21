import logging
import os
import time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class shutdown_NoOpenFilesTestCase(test.test):
  version = 1

  def run_once(self):
    # If the shutdown_force_kill_processes file exists, then a previous
    # shutdown encountered processes with open files on one of our stateful
    # partitions at the time that it wanted to unmount them. The lsof output
    # will be recorded in the shutdown_force_kill_prcesses file for you to
    # inspect.
    filename = "/var/log/shutdown_force_kill_processes"
    if os.path.exists(filename):
      f = open(filename, 'r')
      contents = f.read()
      f.close()
      logging.info("Last shutdown was not clean.  lsof output was:\n%s" %
                   contents)
      os.remove(filename)
      raise error.TestError("Test failed")
