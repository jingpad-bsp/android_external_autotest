# pylint: disable-msg=C0111
# TODO: get rid of above, fix docstrings. crbug.com/273903
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros.graphite import es_utils

try:
    import statsd
except ImportError:
    logging.debug('import statsd failed, no stats will be reported.')
    import statsd_mock as statsd


# Pylint locally complains about "No value passed for parameter 'key'" here
# pylint: disable=E1120
# If one has their hostname listed including a domain, ie. |milleral.mtv|,
# then this will show up on Graphite as milleral/mtv/<stats>.  This seems
# silly, so let's replace '.'s with '_'s to disambiguate Graphite folders
# from FQDN hostnames.
AUTOTEST_SERVER = global_config.global_config.get_config_value(
        'SERVER', 'hostname', default='localhost').replace('.', '_')
STATSD_SERVER = global_config.global_config.get_config_value('CROS',
        'STATSD_SERVER', default='')
STATSD_PORT = global_config.global_config.get_config_value('CROS',
        'STATSD_PORT', type=int, default=0)


def _prepend_server(name, bare=False):
    """
    Since many people run their own local AFE, stats from a local setup
    shouldn't get mixed into stats from prod.  Therefore, this function
    exists to prepend the name of the local server to the stats if |name|
    doesn't start with the server name, so that each person has their own
    "folder" of stats that they can look at.

    However, this functionality might not always be wanted, so we allow
    one to pass in |bare=True| to force us to not prepend the local
    server name. (I'm not sure when one would use this, but I don't see why
    I should disallow it...)

    >>> AUTOTEST_SERVER = 'potato_nyc'
    >>> _prepend_server('rpc.create_job', bare=False)
    'potato_nyc.rpc.create_job'
    >>> _prepend_server('rpc.create_job', bare=True)
    'rpc.create_job'

    @param name The name to append to the server name if it doesn't start
                with the server name.
    @param bare If True, |name| will be returned un-altered.
    @return A string to use as the stat name.

    """
    if not bare and not name.startswith(AUTOTEST_SERVER):
        name = '%s.%s' % (AUTOTEST_SERVER, name)
    return name


# statsd logs details about what its sending at the DEBUG level, which I really
# don't want to see tons of stats in logs, so all of these are silenced by
# setting the logging level for all of statsdto WARNING.
logging.getLogger('statsd').setLevel(logging.WARNING)


# In case someone uses statsd off of site-packages instead of here
# let's still override the defaults in case one starts using clients
# from statsd instead of from here.  It can't hurt?
statsd.Connection.set_defaults(host=STATSD_SERVER, port=STATSD_PORT)


# This is the connection that we're going to reuse for every client that gets
# created.  This should maximally reduce overhead of stats logging.
_conn = statsd.Connection(host=STATSD_SERVER, port=STATSD_PORT)


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

    def __init__(self, name, connection=None, bare=False,
                 metadata=None, index=None,
                 es_host=es_utils.METADATA_ES_SERVER,
                 es_port=es_utils.ES_PORT):
        conn = connection or _conn
        super(Average, self).__init__(_prepend_server(name, bare), conn)
        self.metadata = metadata
        self.index = index
        self.es = es_utils.ESMetadata(es_host, es_port)


    def send(self, subname, value):
        """Sends time-series data to graphite and metadata (if any) to es.

        @param subname: The subname to report the data to (i.e. 'daisy.reboot')
        @param value: Value to be sent.
        """
        super(Average, self).send(subname, value)
        self.es.post(index=self.index, metadata=self.metadata,
                     subname=subname, value=value)

class Counter(statsd.Counter):
    """Wrapper around statsd.Counter."""

    def __init__(self, name, connection=None, bare=False,
                 metadata=None, index=None,
                 es_host=es_utils.METADATA_ES_SERVER,
                 es_port=es_utils.ES_PORT):
        conn = connection or _conn
        super(Counter, self).__init__(_prepend_server(name, bare), conn)
        self.metadata = metadata
        self.index = index
        self.es = es_utils.ESMetadata(es_host, es_port)


    def _send(self, subname, value):
        """Sends time-series data to graphite and metadata (if any) to es.

        @param subname: The subname to report the data to (i.e. 'daisy.reboot')
        @param value: Value to be sent.
        """
        super(Counter, self)._send(subname, value)
        self.es.post(index=self.index, metadata=self.metadata,
                     subname=subname, value=value)

class Gauge(statsd.Gauge):
    """Wrapper around statsd.Gauge."""

    def __init__(self, name, connection=None, bare=False,
                 metadata=None, index=None,
                 es_host=es_utils.METADATA_ES_SERVER,
                 es_port=es_utils.ES_PORT):
        conn = connection or _conn
        super(Gauge, self).__init__(_prepend_server(name, bare), conn)
        self.metadata = metadata
        self.index = index
        self.es = es_utils.ESMetadata(es_host, es_port)


    def send(self, subname, value):
        """Sends time-series data to graphite and metadata (if any) to es.

        @param subname: The subname to report the data to (i.e. 'daisy.reboot')
        @param value: Value to be sent.
        """
        super(Gauge, self).send(subname, value)
        self.es.post(index=self.index, metadata=self.metadata,
                     subname=subname, value=value)


class Timer(statsd.Timer):
    """Wrapper around statsd.Timer."""

    def __init__(self, name, connection=None, bare=False,
                 metadata=None, index=None,
                 es_host=es_utils.METADATA_ES_SERVER,
                 es_port=es_utils.ES_PORT):
        conn = connection or _conn
        super(Timer, self).__init__(_prepend_server(name, bare), conn)
        self.metadata = metadata
        self.index = index
        self.es = es_utils.ESMetadata(es_host, es_port)


    # To override subname to not implicitly append 'total'.
    def stop(self, subname=''):
        super(Timer, self).stop(subname)


    def send(self, subname, value):
        """Sends time-series data to graphite and metadata (if any) to es.

        @param subname: The subname to report the data to (i.e. 'daisy.reboot')
        @param value: Value to be sent.
        """
        super(Timer, self).send(subname, value)
        self.es.post(index=self.index, metadata=self.metadata,
                     subname=subname, value=value)


    def __enter__(self):
        self.start()
        return self


    def __exit__(self, exn_type, exn_value, traceback):
        if exn_type is None:
            self.stop()


class Raw(statsd.Raw):
    """Wrapper around statsd.Raw."""

    def __init__(self, name, connection=None, bare=False,
                 metadata=None, index=None,
                 es_host=es_utils.METADATA_ES_SERVER,
                 es_port=es_utils.ES_PORT):
        conn = connection or _conn
        super(Raw, self).__init__(_prepend_server(name, bare), conn)
        self.metadata = metadata
        self.index = index
        self.es = es_utils.ESMetadata(es_host, es_port)


    def send(self, subname, value, timestamp=None):
        """Sends time-series data to graphite and metadata (if any) to es.

        The datapoint we send is pretty much unchanged (will not be aggregated)

        @param subname: The subname to report the data to (i.e. 'daisy.reboot')
        @param value: Value to be sent.
        @param timestamp: Time associated with when this stat was sent.
        """
        super(Raw, self).send(subname, value, timestamp)
        self.es.post(index=self.index, metadata=self.metadata,
                     subname=subname, value=value, timestamp=timestamp)