# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper functions for testing stats module and elasticsearch
"""

import logging
import time

import common

try:
    import elasticsearch
except ImportError:
    logging.debug('import elasticsearch failed,'
                  'no metadata will be reported.')
    import elasticsearch_mock as elasticsearch

from autotest_lib.client.common_lib.cros.graphite import es_utils
from autotest_lib.client.common_lib.cros.graphite import stats


# Defines methods in the stats class that can take in metadata.
TARGET_TO_STATS_CLASS = {
    'timer': stats.Timer,
    'gauge': stats.Gauge,
    'raw': stats.Raw,
    'average': stats.Average,
    'counter': stats.Counter,
}

# Maps target type to method to trigger sending of metadata.
# This differs based on what each object does.
# For example, in order for timer to send something, its stop
# method must be called. This differs for other stats objects.
TARGET_TO_METHOD = {
    'timer': 'stop',
    'gauge': 'send',
    'raw': 'send',
    'average': 'send',
    'counter': '_send',
}

# Default maximum number of entries to return from ES query
DEFAULT_NUM_ENTRIES = 100

class EsTestUtilException(Exception):
    """Exception raised when functions here fail. """
    pass


def sequential_random_insert_ints(keys, num_entries, target_type, index,
                                  host, port, between_insert_secs=0,
                                  print_interval=10):
    """Inserts a bunch of random entries into the es database.
    Keys are given, values are randomly generated.

    @param keys: A list of keys
    @param num_entries: Number of entries to insert
    @param target_type: This must be in
            ['timer', 'gauge', 'raw', 'average', 'counter']
    @param between_insert_secs: Time to sleep after each insert.
                                defaults to no sleep time.
    @param print_interval: how often to print
                           defaults to every 10 entries.
    @param index: Index of es db to insert to
    @param host: host of es db
    @param port: port of es db
    """
    # We are going to start the value at 0 and increment it by one per val.
    for i in range(num_entries):
        if print_interval == 0 or i % print_interval == 0:
            print('    Inserting entry #%s with keys %s into index "%s."'
                   % (i, str(keys), index))
        metadata = {}
        for value, key in enumerate(keys):
            metadata[key] = value

        # Subname and value are not important from metadata pov.
        subname = 'metadata.test'
        value = 10
        stats_target = TARGET_TO_STATS_CLASS[target_type](subname,
                metadata=metadata,
                index=index,
                es_host=host,
                es_port=port)

        if target_type == 'timer':
            stats_target.start()
            stats_target.stop()
        else:
            getattr(stats_target, TARGET_TO_METHOD[target_type])(subname, value)
        time.sleep(between_insert_secs)


def clear_index(index, host, port, timeout, sleep_time=0.5, clear_timeout=5):
    """Clears index in es db located at host:port.

    Warning: Will delete all data in es for a given index

    @param index: Index of es db to clear
    @param host: elasticsearch host
    @param port: elasticsearch port
    @param timeout: how long to wait while connecting to es.
    @param sleep_time: time between tries of clear_index
                       defaults to 0.5 seconds
    @param clear_timeout: how long to wait for index to be cleared.
                       defualts to 5 seconds
      Will quit and throw error if not cleared. (Number of seconds)
    """
    es = elasticsearch.Elasticsearch(host=host,
                                     port=port,
                                     timeout=timeout)
    if es.indices.exists(index=index):
        print 'deleting index %s' % (index)
        es.indices.delete(index=index)
        time_start = time.time()
        while es.indices.exists(index=index):
            print 'waiting until index is deleted...'
            time.sleep(sleep_time)
            if time.time() - time_start > clear_timeout:
                raise EsTestUtilException('clear_index failed.')

    print 'successfully deleted index %s' % (index)


def create_range_eq_query(fields_returned,
                          equals_key=None,
                          equals_val=None,
                          range_key=None,
                          range_low=None,
                          range_high=None,
                          size=DEFAULT_NUM_ENTRIES,
                          sort_specs=None):
    """Creates a dict. representing range and/or equality queries.

    @param fields_returned: list of fields that we should return when
                            the query is executed
    @param equals_key: Key that we filter based on equality. default=None
    @param equals_val: value we want equals_key to be equal to. default=None
    @param range_key: Key that we filter based on range. default=None
    @param range_low: lower bound on the range_key (inclusive). default=None
    @param range_high: upper bound on the range key (inclusive). default=None
    @param size: max number of entries to return. default=100
    @param sort_specs: A list of fields to sort on, tiebreakers will be
        broken by the next field(s). default=None

    @returns: dictionary representing query.
              Returns none if there is no equals_key or range_key provided.

    Example usage:
    range_eq_query = create_range_eq_query(
        ['job_id', 'host_id', 'job_start'],
        equals_key='host_id', equals_val=10,
        range_key='job_id', range_low=0, range_high=99999)

    Output:
    {
        'fields': ['job_id', 'host_id', 'job_start'],
            'query': {
                'bool': {
                    'minimum_should_match': 2,
                    'should': [
                        {
                            'term':  {
                                'host_id': 10,
                            }
                        },

                        {   
                            'range': {
                                'job_id': {
                                    'gte': 0,
                                    'lte': 99999,
                                }
                            }
                        }
                    ]
                }
            },
        'size': 20
        'sort': [ ]
    }
    """
    if not equals_key and not range_key:
        raise EsTestUtilException('No range_key or equals_key specified.')
    equality_constraints = [(equals_key, equals_val)] if equals_key else []
    range_constraints = []
    if range_key:
        range_constraints = [(range_key, range_low, range_high)]
    return es_utils.create_range_eq_query_multiple(
        equality_constraints=equality_constraints,
        fields_returned=fields_returned,
        range_constraints=range_constraints,
        size=size,
        sort_specs=sort_specs,
    )