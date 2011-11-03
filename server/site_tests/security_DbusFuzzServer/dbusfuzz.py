#!/usr/bin/env python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Style note: dbusfuzz.py is a stand-alone tool independent of autotest.
# It should adhere to PEP-8, rather than local autotest style.

"""Perform API Fuzzing of DBus interfaces."""

import dbus
import optparse
import logging
import subprocess
import sys

class LoggedDbus(object):
    """Convenience wrapper around dbus, adds pretend-mode and logging."""

    def __init__(self, bus=dbus.SystemBus(), logger=logging.debug,
                 pretend=False):
        self.bus = bus
        self.logger = logger
        self.pretend = pretend
        self.runcount = 0


    def _GetBareMethod(self, dest, path, iface, method):
        """Get a reference to the specified DBus method."""
        remote_object = self.bus.get_object(dest, path)
        method_ref = remote_object.get_dbus_method(method, dbus_interface=iface)
        return method_ref


    def _LogCall(self, dest, path, iface, method, *args):
        self.logger('TEST #%d: %s %s %s->%s with %s',
                    self.runcount, dest, path, iface, method, repr(args))


    def GetMethod(self, dest, path, iface, method):
        """Return a (wrapped, for logging) reference to the a DBus method."""
        if not self.pretend:
            method_ref = self._GetBareMethod(dest, path, iface, method)
        # Work around python's lack of multi-line lambdas.
        wrapped_method = lambda *args: [
          self._LogCall(dest, path, iface, method, args),
          None if self.pretend else apply(method_ref, args)
        ][1]
        return wrapped_method


class ProcessMonitor(object):
    """Watch for target process to disappear."""
    # TODO(jimhebert) Determine if we would be better served with
    # a deeper process monitoring strategy, e.g. one based on
    # python-ptrace. If so, borrow or write one as needed.

    def __init__(self, process_name):
        self.process_name = process_name
        self.pids = self._Pids()

        if not self.pids:
            raise Exception('No processes by that name, nothing to monitor')

        logging.debug('Found pids for %s: %s' %
                      (self.process_name, ', '.join(self.pids)))


    def _Pids(self):
        # Look up (potentially multiple) pid(s). This helps when fuzzing
        # e.g. udisks-daemon, which runs 2 processes, and we don't want to
        # have to guess which one to care about. Would not work very well
        # if we were fuzzing something like Apache where child processes
        # come and go naturally.
        try:
            return set(subprocess.Popen(['pgrep', self.process_name],
                                        stdout=subprocess.PIPE
                                        ).communicate()[0].splitlines())
        except subprocess.CalledProcessError:
            return set([])


    def Fault(self):
        """Returns a boolean indicating if your monitored process
           has died since you began monitoring. Returns True if so,
           even if the process was restarted by e.g. init.
        """
        return self.pids != self._Pids()


class BaseMutator(object):
    """Base class for Mutators. Not intended to be used directly."""
    def __init__(self, orig_val):
        self.orig_val = orig_val


    def Mutations(self):
        """Stub. Implement datatype-specific mutations in your sub-classes.
           Callers of Mutations depend on the original value being yielded
           first.
        """
        yield self.orig_val


class Uint32Mutator(BaseMutator):
    """Mutator for the DBus 'uint32' type."""
    def Mutations(self):
        yield self.orig_val
        # This Mutator tends to produce redundant test cases, especially
        # between the bit-flip round and the boundary-case round.
        # Accumulate all of the values and enforce uniqueness before
        # returning any of them.
        mutations = set([])
        mutations.add(0)
        # Flip individual bits.
        for i in range(32):
            mutations.add(self.orig_val ^ (1 << i))
        # Look for boundary cases.
        for i in range(33):
            val = 1 << i
            mutations.add(val-1)
            mutations.add(val)
            mutations.add(val+1)
        # Now yield all the mutations. Ensure we do not repeat the orig_val.
        if self.orig_val in mutations:
            mutations.remove(self.orig_val)
        for m in sorted(mutations):
            yield m


class BoolMutator(BaseMutator):
    """Included for the sake of completeness."""
    def Mutations(self):
        """Returns a generator, yielding both boolean values. In order to
           remain consistent with other Mutators, returns the original
           value first, as a 'good' value.
        """
        # With the current "change 1 variable at a time" mutation strategy,
        # this is of questionable value, but later if we enable the fuzzing
        # engine to do, say, every possible combination of (A x B) mutations,
        # then this could help increase the coverage gained from those mutated
        # values, by exposing them to some "True" and "False" codepaths.
        yield self.orig_val
        yield (not self.orig_val)


class StringMutator(BaseMutator):
    """Basic string mutator to generate fuzzy inputs."""
    # TODO(jimhebert) continue to look for an existing string
    # mutator from some other package that is loosely-coupled
    # enough to be re-used here. Or give up and build this
    # one out, since this is basically no more than a dumb
    # placeholder right now.
    LENGTH_FACTOR = 17

    def Mutations(self):
        """Returns a generator, yielding a series of mutated test strings."""
        yield self.orig_val

        for i in range(self.LENGTH_FACTOR):
            yield (self.orig_val + ('A' * (1 << i)))


class DbusFuzzer(object):
    """Main class encapsulating the DBus Fuzzer."""
    # Some constants returned by FuzzerMain
    PASS = 'PASS'
    FAIL = 'FAIL'
    DONE = 'DONE'


    def __init__(self, logged_dbus, start_at=0, stop_at=None):
        self.bus = logged_dbus
        self.start_at = start_at
        self.stop_at = stop_at


    def ArglistPermutations(self, args):
        """Given a list of arguments, this function returns a generator
        that you can iterate to get mutations of the argument list.

        Items from the argument list which, themselves, are generators,
        are themselves iterated, one at a time. Generator arguments should
        yield some "good" value as their first yield, since it will be used
        repeatedly. The "bad" values -- the rest of them -- will be used once.

        The permutations are generated with a "change only 1 variable at a
        time" strategy. E.g. in a 3-item arglist, you will get permutations
        like:

        [good1, good2, good3]
        [mutation1, good2, good3]
        [mutation2, good2, good3]
        ... until the first argument's generator is exhausted. Then:
        [good1, mutation1, good3]
        [good1, mutation2, good3]
        ... and so on.

        Items which are not generators are taken to be "fixed," non-mutating
        arguments.
        """
        # Save off the first yields from each of the args, since we'll
        # need them repeatedly and only have one chance to save them.
        base_args = []
        for arg in args:
            if hasattr(arg, 'next'):
                base_args.append(arg.next())
            else: # for fixed, non-mutation-generator args.
                base_args.append(arg)

        # Emit this case, since this is a valid permutation, before moving
        # on to further mutations.
        yield base_args

        # Now we need to target each slot in the arglist, one at a time,
        # yielding a series of permutations as described in the docstring.
        slotnum = 0
        while slotnum < len(args):
            mutated_args = base_args[:]
            if hasattr(args[slotnum], 'next'):
                for mutation in args[slotnum]:
                    mutated_args[slotnum] = mutation
                    yield mutated_args
            # Else, the non-mutated form was already emitted by the first yield
            # above, so nothing to do in that case.
            slotnum += 1


    def FuzzerMain(self, fuzzplan):
        """Main entry point for the fuzzer.
           Bails at the first fault detected.
           Returns the highest test # executed, so you can restart at n+1
           later if you wish.
        """

        # For lack of interest in inventing Yet Another config file
        # syntax to express a fuzz plan, FuzzerMain currently expects
        # a big data structure like the the following. When we're
        # farther along and feel confident we've identified all of what
        # we'd want to be able to express in a fuzz plan, then we can
        # figure out a more forward-supportable format for the plan that
        # isn't so tightly coupled to the logic in FuzzerMain.

        # Example fuzzplan:
        #fuzzplan = {
        #  'udisks-daemon': {  # daemon process name as seen in 'ps'
        #    'org.freedesktop.UDisks': { # dbus destination
        #      '/org/freedesktop/UDisks': { # dbus 'path'
        #        'org.freedesktop.DBus.Properties': [ # Interface
        #          ['GetAll', dbus.String('org.freedesktop.UDisks')],
        #          ['Get', dbus.String('org.freedesktop.UDisks'),
        #           StringMutator('SupportsLuksDevices').Mutations()]
        #        ]
        #        ... more interfaces
        #      }
        #      ... other paths
        #    }
        #    ... other destinations
        #  }
        #  ... other processes
        #}
        for process, dests in fuzzplan.items():
            monitor = ProcessMonitor(process)
            for dest, paths in dests.items():
                for path, interfaces in paths.items():
                    for interface, methodcalls in interfaces.items():
                        for methodcall in methodcalls:
                            method = methodcall[0]
                            arglist = methodcall[1:]
                            meth = self.bus.GetMethod(dest, path, interface,
                                                      method)
                            # Iterate all the mutations.
                            for testargs in self.ArglistPermutations(arglist):
                                # Fast forward over this if start_at demands it.
                                if self.bus.runcount < self.start_at:
                                    self.bus.runcount += 1
                                    continue
                                # Work starts here.
                                try:
                                    apply(meth, testargs)
                                except dbus.DBusException as e:
                                    # Might be useful to log this?
                                    pass
                                if monitor.Fault():
                                    logging.error("%s fault after test #%d." %
                                                  (process, self.bus.runcount))
                                    return (self.FAIL, self.bus.runcount)
                                if (self.stop_at != None and
                                    self.bus.runcount >= self.stop_at):
                                    return (self.PASS, self.bus.runcount)
                                self.bus.runcount += 1

        return (self.DONE, self.bus.runcount - 1)


def main():
    programhelp = '%prog - Fuzz dbus interfaces according to a specified plan.'
    parser = optparse.OptionParser(usage='usage: %prog [options] fuzzplan',
                                   description=programhelp)
    parser.add_option('-s', '--start_at', default=0, type='int',
                      help='Testcase number to start on, e.g. 0')
    parser.add_option('-e', '--stop_at', default=None, type='int',
                      help='Testcase number to stop on.')
    parser.add_option('-p', '--pretend', default=False,
                      action='store_true',
                      help='Pretend mode. Do everything except the dbus calls.')
    (options, inputs) = parser.parse_args()
    fuzzplan = None
    # TODO(jimhebert) replace with routine to read some "real" file format.
    # See also: longer comment on fuzzplan file format future, in FuzzerMain.
    exec(file(inputs[0]).read())

    # TODO(jimhebert) add a command line logging option that takes a filename.
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    bus = LoggedDbus(pretend=options.pretend)
    fuzzer = DbusFuzzer(bus, start_at=options.start_at,
                        stop_at=options.stop_at)
    print "%s:%s" % fuzzer.FuzzerMain(fuzzplan)


if __name__ == '__main__':
    main()
