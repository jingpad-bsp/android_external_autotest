# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dpkt
import os
import select
import struct
import threading
import time


class SimulatorError(Exception):
    "A Simulator generic error."


class Simulator(object):
    """A TUN/TAP network interface simulator class.

    This class allows several implementations of different fake hosts to
    coexists on the same TUN/TAP interface. It will dispatch the same packet
    to each one of the registered hosts, providing some basic filtering
    to simplify these implementations.
    """

    def __init__(self, iface):
        """Initialize the instance.

        @param tuntap.TunTap iface: the interface over which this interface
        runs. Should not be shared with other modules.
        """
        self._iface = iface
        self._rules = []
        # _events holds a lists of events that need to be fired for each
        # timestamp stored on the key. The event list is a list of callback
        # functions that will be called if the simulation reaches that
        # timestamp. This is used to fire time-based events.
        self._events = {}
        self._write_queue = []
        # A pipe used to wake up the run() method from a diffent thread calling
        # stop(). See the stop() method for details.
        self._pipe_rd, self._pipe_wr = os.pipe()
        self._running = False


    def __del__(self):
        os.close(self._pipe_rd)
        os.close(self._pipe_wr)


    def add_match(self, rule, callback):
        """Add a new match rule to the outbound traffic.

        This function adds a new rule that will be matched against each packet
        that the host sends through the interface and will call a callback if
        it matches. The rule can be specified in the following ways:
          * A python function that takes a packet as a single argument and
            returns True when the packet matches.
          * A dictionary of key=value pairs that all of them need to be matched.
            A pair matches when the packet has the provided chain of attributes
            and its value is equal to the provided value. For example, this will
            match any DNS traffic sent to the host 192.168.0.1:
            {"ip.dst": socket.inet_aton("192.168.0.1"),
             "ip.upd.dport": 53}

        @param rule: The rule description.
        @param callback: A callback function that receives the dpkt packet as
        the only argument.
        """
        if not callable(callback):
            raise SimulatorError("|callback| must be a callable object.")

        if callable(rule):
            self._rules.append((rule, callback))
        if isinstance(rule, dict):
            rule = dict(rule) # Makes a copy of the dict, but not the contents.
            self._rules.append((lambda p: self._dict_rule(rule, p), callback))
        else:
            raise SimulatorError("Unknown rule format: %r" % rule)


    def add_timeout(self, timeout, callback):
        """Add a new callback function to be called after a timeout.

        This method schedules the given |callback| to be called after |timeout|
        seconds. The callback will be called at most once while the simulator
        is running (see the run() method). To have a repetitive event call again
        add_timeout() from the callback.

        @param timeout: The rule description.
        @param callback: A callback function that doesn't receive any argument.
        """
        if not callable(callback):
            raise SimulatorError("|callback| must be a callable object.")
        timestamp = time.time() + timeout
        if timestamp not in self._events:
            self._events[timestamp] = [callback]
        else:
            self._events[timestamp].append(callback)


    def _dict_rule(self, rules, pkt):
        """Returns wether a given packet matches a set of rules.

        The maching rules passed in |rules| need to be a dict() as described
        on the add_match() method. The packet |pkt| is any dpkt packet.
        """
        for key, value in rules.iteritems():
            p = pkt
            for member in key.split('.'):
                if not hasattr(p, member):
                    return False
                p = getattr(p, member)
            if p != value:
                return False
        return True


    def write(self, pkt):
        """Writes a packet to the network interface.

        @param pkt: The dpkt.Packet to be received on the network interface.
        """
        # Converts the dpkt packet to: flags, proto, buffer.
        self._write_queue.append(struct.pack("!HH", 0, pkt.type) + str(pkt))


    def run(self, timeout=None):
        """Runs the Simulator.

        This method blocks the caller thread until the timeout is reached (if
        a timeout is passed) or until stop() is called. stop() can be called
        from any other thread or from a callback called from this thread.

        @param timeout: The timeout in seconds. Can be a float value, or None
        for no timeout.
        """
        if not self._iface.is_up():
            raise SimulatorError("Interface is down.")

        if timeout != None:
            self.add_timeout(timeout, lambda: self.stop())

        self._running = True
        iface_fd = self._iface.fileno()
        while self._running:
            # The main purpose of this loop is to wait (block) until the next
            # event is required to be fired. There are four kinds of events:
            #  * a packet is received.
            #  * a packet waiting to be sent can now be sent.
            #  * a time-based event needs to be fired.
            #  * the simulator was stopped from a different thread.
            # To achieve this we use select.select() to wait simultaneously on
            # all those event sources.

            # Fires all the time-based events that need to be fired and computes
            # the timeout for the next event if there's one.
            timeout = None
            cur_time = time.time()
            if self._events:
                # Check events that should be fired.
                while self._events and min(self._events) <= cur_time:
                    key = min(self._events)
                    lst = self._events[key]
                    del self._events[key]
                    for callback in lst:
                        callback()
                    cur_time = time.time()
            # Check if there is an event to attend. Here we know that
            # min(self._events) > cur_time because the previous while finished.
            if self._events:
                timeout = min(self._events) - cur_time # in seconds

            # Compute the list of file descriptors that select.select() needs to
            # monitor to attend the required events. select() will return when
            # any of the following occurs:
            #  * rlist: is possible to read from the interface or another
            #           thread want's to wake up the simulator loop.
            #  * wlist: is possible to write to network, if there's a packet
            #           pending.
            #  * xlist: an error on the network fd occured. Likely the TAP
            #           interface was closed.
            #  * timeout: The previously computed timeout was reached.
            rlist = iface_fd, self._pipe_rd
            wlist = tuple()
            if self._write_queue:
                wlist = iface_fd,
            xlist = iface_fd,

            rlist, wlist, xlist = select.select(rlist, wlist, xlist, timeout)

            if self._pipe_rd in rlist:
                # stop() was called.
                os.read(self._pipe_rd, 1)
                break

            if xlist:
                break

            if iface_fd in wlist:
                self._iface.write(self._write_queue.pop(0))
                # Attempt to send all the scheduled packets before reading more
                continue

            # Process the given packet:
            if iface_fd in rlist:
                raw = self._iface.read()
                flag, proto = struct.unpack("!HH", raw[:4])
                pkt = dpkt.ethernet.Ethernet(raw[4:])
                for rule, callback in self._rules:
                    if rule(pkt):
                        callback(pkt)

        self._running = False


    def stop(self):
        """Stops the run() method if it is running."""
        if self._running:
            self._running = False
            os.write(self._pipe_wr, '*')


class SimulatorThread(threading.Thread, Simulator):
    """A threaded version of the Simulator.

    This class exposses a similar interface as the Simulator class with the
    difference that it runs on its own thread. This exposes an extra method
    start() that should be called instead of Simulator.run(). start() will make
    the process run continuosly until stop() is called, after which the
    simulator can't be restarted.

    The methods used to add new matches can be called from any thread *before*
    the method start() is caller. After that point, only the callbacks, running
    from this thread, are allowed to create new matches and timeouts.

    Example:
        simu = SimulatorThread(tap_interface)
        simu.add_match({"ip.tcp.dport": 80}, some_callback)
        simu.start()
        time.sleep(100)
        simu.stop()
        simu.join() # Optional
    """

    def __init__(self, iface, timeout=None):
        threading.Thread.__init__(self)
        Simulator.__init__(self, iface)
        self._timeout = timeout
        self.error = None


    def run(self):
        """Runs the simulation on the thread, called by start().

        This method wraps the Simulator.run() to pass the timeout value passed
        during construction.
        """
        try:
            Simulator.run(self, self._timeout)
        except Exception, e:
            self.error = e
