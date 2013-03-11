# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import socket

import common

import statsd
from autotest_lib.client.common_lib import global_config


# Pylint locally complains about "No value passed for parameter 'key'" here
# pylint: disable=E1120
# If one has their hostname listed including a domain, ie. |milleral.mtv|,
# then this will show up on Graphite as milleral/mtv/<stats>.  This seems
# silly, so let's replace '.'s with '_'s to disambiguate Graphite folders
# from FQDN hostnames.
AUTOTEST_SERVER = global_config.global_config.get_config_value(
        'SERVER', 'hostname', default='localhost').replace('.', '_')
STATSD_SERVER = global_config.global_config.get_config_value('CROS',
        'STATSD_SERVER')
STATSD_PORT = global_config.global_config.get_config_value('CROS',
        'STATSD_PORT', type=int)


def _prepend_server(name, bare=False):
    """
    Since many people run their own local AFE, stats from a local setup
    shouldn't get mixed into stats from prod.  Therefore, this function
    exists to prepend the name of the local server to the stats, so that
    each person has their own "folder" of stats that they can look at.

    However, this functionality might not always be wanted, so we allow
    one to pass in |bare=True| to force us to not prepend the local
    server name. (I'm not sure when one would use this, but I don't see why
    I should disallow it...)

    >>> AUTOTEST_SERVER = 'potato_nyc'
    >>> _prepend_server('rpc.create_job', bare=False)
    'potato_nyc.rpc.create_job'
    >>> _prepend_server('rpc.create_job', bare=True)
    'rpc.create_job'

    @param name The name to append to the server name.
    @param bare If True, |name| will be returned un-altered.
    @return A string to use as the stat name.

    """
    if not bare:
        name = '%s.%s' % (AUTOTEST_SERVER, name)
    return name


class _SendallSocket(socket.socket):
    """
    This is the special sauce used in Connection below to redirect calls from
    |udp_socket.sendto()| to |udp_socket.sendall|, as we've injected a
    |connect()| call.
    """


    def sendto(self, data, host_port):
        """
        This method gets replaces |udpsock.sendto| to make it ignore
        the (host, port) argument, and redirect the data to sendall().

        @param data The data to send.
        @param host_port IGNORED.
        @return The result of sending the data.

        """
        return self.sendall(data)


class Connection(statsd.Connection):
    """
    A statsd connection that actually |connect()|s.

    The implementation in statsd will incur a DNS lookup every time that we
    send stats.  We've already had issues where frequent DNS lookups might
    fail, and a DNS lookup is a non-insignificant amount of time when
    measuring runtimes already in the millisecond range.

    """


    def __init__(self, host=None, port=None, sample_rate=None, disabled=None):
        """
        Extends statsd.Connection by connecting to the remote host.

        @param host The host running statsd.
        @param port The port statsd is running on.
        @param sample_rate How frequently to send collected data.
        @param disabled If True, never send data.
        """
        super(Connection, self).__init__(host, port, sample_rate, disabled)
        # In statsd.Connection.send(), there's a call to sendto() that I want
        # to override.  My two options are either lift the function wholesale,
        # which seems sad, or do something to change what calling sendto()
        # does.  The route taken here is to subclass socket and replace
        # |udp_sock| with a socket that redirects sendto() calls to sendall().
        self.udp_sock.close()
        self.udp_sock = _SendallSocket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.udp_sock.connect((self._host, self._port))
        except EnvironmentError as e:
            self.logger.exception(e)


    def send(self, data, sample_rate=None):
        """
        Extends statsd.Connection by catching a |socket.error| if it's thrown.

        If chrmoeos-stats is down, then we'll get a connection refused error
        when we try to send data.  This is represented by a |socket.error|
        exception.  If this happens, we don't want to take down any service, so
        let's catch and log the output.  Note that the logging info will be
        likely ignored as it's logged at the DEBUG level when we set the logger
        to WARNING in __init__.

        @param data The data to send to statsd.
        @param sample_rate How frequently to send collected data.
        @return The result of statsd.Connection.send()

        """
        try:
            super(Connection, self).send(data, sample_rate)
        except socket.error as e:
            self.logger.debug(str(e))
            return False


# In case someone uses statsd off of site-packages instead of here
# let's still override the defaults in case one starts using clients
# from statsd instead of from here.  It can't hurt?
statsd.Connection.set_defaults(host=STATSD_SERVER, port=STATSD_PORT)


# This is the connection that we're going to reuse for every client that gets
# created.  This should maximally reduce overhead of stats logging.
_conn = Connection(host=STATSD_SERVER, port=STATSD_PORT)


# We now need to wrap around the stats in statsd so that the server name gets
# automagically prepended.

# I was tempted to do this as just factory functions, ie.
#   def Average(name, bare): return statsd.Average(_prepended(name, bare))
# but then we'd have things that look like a class and wrap a class but
# is not a class and that feels confusing. And
#   Average = _prepend_to_stat(statsd.Average)
# just feels like too much magic, so we're left with lots of mini-classes.


class Average(statsd.Average):
    """Wrapper around statsd.Average."""
    def __init__(self, name, bare=False):
        super(Average, self).__init__(_prepend_server(name, bare), _conn)
        # statsd logs details about what its sending at the DEBUG level,
        # which I really don't want to see tons of stats in logs, so all
        # of these are silenced by setting the logging level to WARNING.
        self.logger.setLevel(logging.WARNING)


class Counter(statsd.Counter):
    """Wrapper around statsd.Counter."""
    def __init__(self, name, bare=False):
        super(Counter, self).__init__(_prepend_server(name, bare), _conn)
        self.logger.setLevel(logging.WARNING)


class Gauge(statsd.Gauge):
    """Wrapper around statsd.Gauge."""
    def __init__(self, name, bare=False):
        super(Gauge, self).__init__(_prepend_server(name, bare), _conn)
        self.logger.setLevel(logging.WARNING)


class Timer(statsd.Timer):
    """Wrapper around statsd.Timer."""
    def __init__(self, name, bare=False):
        super(Timer, self).__init__(_prepend_server(name, bare), _conn)
        self.logger.setLevel(logging.WARNING)


class Raw(statsd.Raw):
    """Wrapper around statsd.Raw."""
    def __init__(self, name, bare=False):
        super(Raw, self).__init__(_prepend_server(name, bare), _conn)
        self.logger.setLevel(logging.WARNING)
