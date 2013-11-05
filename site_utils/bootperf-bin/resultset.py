# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes and functions for managing platform_BootPerf results.

Results from the platform_BootPerf test in the ChromiumOS autotest
package are stored as performance 'keyvals', that is, a mapping
of names to numeric values.  For each iteration of the test, one
set of keyvals is recorded.

This module currently tracks three kinds of keyval results: the boot
time results, the disk read results, and firmware time results.
These results are stored with keyval names such as
'seconds_kernel_to_login', 'rdbytes_kernel_to_login', and
'seconds_power_on_to_kernel'.  These keyvals record an accumulated
total measured from a fixed time in the past, e.g.
'seconds_kernel_to_login' records the total seconds from kernel
startup to login screen ready.

The boot time keyval names all start with the prefix
'seconds_kernel_to_', and record time in seconds since kernel
startup.

The disk read keyval names all start with the prefix
'rdbytes_kernel_to_', and record bytes read from the boot device
since kernel startup.

The firmware keyval names all start with the prefix
'seconds_power_on_to_', and record time in seconds since CPU
power on.

"""

import math


def _ListStats(list_):
  # Utility function - calculate the average and (sample) standard
  # deviation of a list of numbers.  Result is float, even if the
  # input list is full of int's
  sum_ = 0.0
  sumsq = 0.0
  for v in list_:
    sum_ += v
    sumsq += v * v
  n = len(list_)
  avg = sum_ / n
  var = (sumsq - sum_ * avg) / (n - 1)
  if var < 0.0:
    var = 0.0
  dev = math.sqrt(var)
  return (avg, dev)


def _DoCheck(dict_):
  # Utility function - check the that all keyvals occur the same
  # number of times.  On success, return the number of occurrences;
  # on failure return None
  check = map(len, dict_.values())
  if not check:
    return None
  for i in range(1, len(check)):
    if check[i] != check[i-1]:
      return None
  return check[0]


def _KeyDelta(dict_, key0, key1):
  # Utility function - return a list of the vector difference between
  # two keyvals.
  return map(lambda a, b: b - a, dict_[key0], dict_[key1])


class TestResultSet(object):
  """A set of boot time and disk usage result statistics.

  Objects of this class consist of three sets of result statistics:
  the boot time statistics, the disk statistics, and the firmware
  time statistics.

  Class TestResultsSet does not interpret or store keyval mappings
  directly; iteration results are processed by attached _KeySet
  objects, one for each of the three types of result keyval. The
  _KeySet objects are kept in a dictionary; they can be obtained
  by calling the KeySet with the name of the keyset desired.
  Various methods on the KeySet objects will calculate statistics on
  the results, and provide the raw data.

  """

  # The names of the available KeySets, to be used as arguments to
  # KeySet().
  BOOTTIME_KEYSET = "time"
  DISK_KEYSET = "disk"
  FIRMWARE_KEYSET = "firmware"

  def __init__(self, name):
    self.name = name
    self._keysets = {
      self.BOOTTIME_KEYSET : _TimeKeySet(),
      self.DISK_KEYSET : _DiskKeySet(),
      self.FIRMWARE_KEYSET : _FirmwareKeySet(),
    }

  def AddIterationResults(self, runkeys):
    """Add keyval results from a single iteration.

    A TestResultSet is constructed by repeatedly calling
    AddIterationResults(), iteration by iteration.  Iteration
    results are passed in as a dictionary mapping keyval attributes
    to values.  When all iteration results have been added,
    FinalizeResults() makes the results available for analysis.

    """

    for keyset in self._keysets.itervalues():
      keyset.AddIterationResults(runkeys)

  def FinalizeResults(self):
    """Make results available for analysis.

    A TestResultSet is constructed by repeatedly feeding it results,
    iteration by iteration.  Iteration results are passed in as a
    dictionary mapping keyval attributes to values.  When all iteration
    results have been added, FinalizeResults() makes the results
    available for analysis.

    """

    for keyset in self._keysets.itervalues():
      keyset.FinalizeResults()

  def KeySet(self, keytype):
    """Return the boot time statistics result set."""
    return self._keysets[keytype]


class _KeySet(object):
  """Container for a set of related statistics.

  _KeySet is an abstract superclass for containing collections of
  a related set of performance statistics.  Statistics are stored
  as a dictionary (`_keyvals`) mapping keyval names to lists of
  values.  The lists are indexed by the iteration number.

  The mapped keyval names are shortened by stripping the prefix
  that identifies the type of keyval (keyvals that don't start with
  the proper prefix are ignored).  So, for example, with boot time
  keyvals, 'seconds_kernel_to_login' becomes 'login' (and
  'rdbytes_kernel_to_login' is ignored).

  A list of all valid keyval names is stored in the `markers`
  instance variable.  The list is sorted by the ordering of the
  average of the corresponding values.  Each iteration is required
  to contain the same set of keyvals.  This is enforced in
  FinalizeResults() (see below).

  """

  def __init__(self):
    self._keyvals = {}

  def AddIterationResults(self, runkeys):
    """Add results for one iteration."""

    for key, value in runkeys.iteritems():
      if not key.startswith(self.PREFIX):
        continue
      shortkey = key[len(self.PREFIX):]
      keylist = self._keyvals.setdefault(shortkey, [])
      keylist.append(self._ConvertVal(value))

  def FinalizeResults(self):
    """Finalize this object's results.

    This method makes available the `markers` and `num_iterations`
    instance variables.  It also ensures that every keyval occurred
    in every iteration by requiring that all keyvals have the same
    number of data points.

    """

    count = _DoCheck(self._keyvals)
    if count is None:
      self.num_iterations = 0
      self.markers = []
      return False
    self.num_iterations = count
    keylist = map(lambda k: (sum(self._keyvals[k]), k),
                  self._keyvals.keys())
    keylist.sort(key=lambda tp: tp[0])
    self.markers = map(lambda tp: tp[1], keylist)
    return True

  def RawData(self, key):
    """Return the list of values for the given marker key."""
    return self._keyvals[key]

  def DeltaData(self, key0, key1):
    """Return vector difference of the values of the given keys."""
    return _KeyDelta(self._keyvals, key0, key1)

  def Statistics(self, key):
    """Return the average and standard deviation of the key's values."""
    return _ListStats(self._keyvals[key])

  def DeltaStatistics(self, key0, key1):
    """Return the average and standard deviation of the differences
    between two keys.

    """
    return _ListStats(self.DeltaData(key0, key1))


class _TimeKeySet(_KeySet):
  """Concrete subclass of _KeySet for boot time statistics."""

  PREFIX = 'seconds_kernel_to_'

  # Time-based keyvals are reported in seconds and get converted to
  # milliseconds
  TIME_SCALE = 1000

  def _ConvertVal(self, value):
    # We want to return the nearest exact integer here.  round()
    # returns a float, and int() truncates its results, so we have
    # to combine them.
    return int(round(self.TIME_SCALE * float(value)))

  def PrintableStatistic(self, value):
    v = int(round(value))
    return ("%d" % v, v)


class _FirmwareKeySet(_TimeKeySet):
  """Concrete subclass of _KeySet for firmware time statistics."""

  PREFIX = 'seconds_power_on_to_'

  # Time-based keyvals are reported in seconds and get converted to
  # milliseconds
  TIME_SCALE = 1000


class _DiskKeySet(_KeySet):
  """Concrete subclass of _KeySet for disk read statistics."""

  PREFIX = 'rdbytes_kernel_to_'

  # Disk read keyvals are reported in bytes and get converted to
  # MBytes (1 MByte = 1 million bytes, not 2**20)
  DISK_SCALE = 1.0e-6

  def _ConvertVal(self, value):
    return self.DISK_SCALE * float(value)

  def PrintableStatistic(self, value):
    v = round(value, 1)
    return ("%.1fM" % v, v)
