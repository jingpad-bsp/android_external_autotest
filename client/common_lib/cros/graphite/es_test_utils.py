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


class EsTestUtilException(Exception):
    """Exception raised when functions here fail. """
    pass


# TODO: Point to test es instance, instead of prod.
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
    @param print_interval: how often to print
    @param index: Index of es db to insert to
    @param host: host of es db
    @param port: port of es db
    """
    # We are going to start the value at 0 and increment it by one per val.
    for i in range(num_entries):
        if print_interval == 0 or i % print_interval == 0:
            print ('    Inserting entry #%s with keys %s into index "%s."'
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
    @param clear_timeout: how long to wait for index to be cleared.
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
                          range_high=None):
    """Creates a dict. representing range and/or equality queries.

    @param fields_returned: list of fields that we should return when
                            the query is executed
    @param equals_key: Key that we filter based on equality.
    @param equals_val: value we want equals_key to be equal to.
    @param range_key: Key that we filter based on range
    @param range_low: lower bound on the range_key (inclusive)
    @param range_high: upper bound on the range key (inclusive)

    @returns: dictionary representing query.

    Example usage:
    range_eq_query = create_range_eq_query(
        ['job_id', 'host_id', 'job_start'],
        equals_key='host_id', equals_val=10,
        range_key='job_id', range_low=0, range_high=99999)

    Output:
    {
        'fields': ['job_id', 'host_id', 'job_start'],
        'query': {
            'filtered': {
                'query': {
                    'match': {
                        'host_id': 10,
                    }
                }
                'filter': {
                    'range': {
                        'job_id': {
                            'gte': 0,
                            'lte': 99999,
                        }
                    }
                }
            }
        }
    }

    TODO(michaelliang): equals_key: make this support more than 1 equality key
    TODO(michaelliang): range_key: make this support more than 1 range key
    """
    if not equals_key and not range_key:
        logging.warn('No range_key or equals_key specified...')
        return
    filtered_terms = {}
    if equals_key:
        filtered_terms['match'] = {equals_key: equals_val}
    if range_key:
        filtered_terms['range'] = {}
        filtered_terms['range'][range_key] = {}
        if range_low != None:
            filtered_terms['range'][range_key]['gte'] = range_low
        if range_high != None:
            filtered_terms['range'][range_key]['lte'] = range_high
    return _create_query(fields_returned, filtered_terms)


def _create_query(fields_returned, filtered_terms):
    """Helper method for create_range_query

    @param fields_returned: list of fields to return
    @param filtered_terms: dict where keys can be 'match' and/or 'range'
        and value is dict contains information about what to match or
        within what range. For example:
        {
            'match': {
                'host_id': 10,
            }
            'range': {
                'job_id': {
                    'gte': 0,
                    'lte': 99999,
                }
            }
        }
    @returns: query string
    """
    range_dict = {}
    filtered_dict = {}
    if 'range' in filtered_terms:
        range_dict['range'] = filtered_terms['range']
        filtered_dict['filter'] = range_dict
    match_dict = {}
    if 'match' in filtered_terms:
        match_dict['match'] = filtered_terms['match']
        filtered_dict['query'] = match_dict

    query_base = {
        'fields': fields_returned,
        'query' : {
            'filtered' : filtered_dict,
        }
    }
    return query_base


def execute_query(query, index, host, port, timeout=3):
    """Makes a query on the given index.

    @param query: query dictionary (see create_range_query)
    @param index: index within db to query
    @param host: host running es
    @param port: port running es
    @param timeout: seconds to wait before es retries if conn. fails.
    @returns: dictionary of the results, or None if index does not exist.

    Example output:
    {
      "took" : 5,
      "timed_out" : false,
      "_shards" : {
        "total" : 16,
        "successful" : 16,
        "failed" : 0
      },
      "hits" : {
        "total" : 4,
        "max_score" : 1.0,
        "hits" : [ {
          "_index" : "graphite_metrics2",
          "_type" : "metric",
          "_id" : "rtntrjgdsafdsfdsfdsfdsfdssssssss",
          "_score" : 1.0,
          "_source":{"target_type": "timer",
                     "host_id": 1,
                     "job_id": 22,
                     "time_start": 400}
        }, {
          "_index" : "graphite_metrics2",
          "_type" : "metric",
          "_id" : "dfgfddddddddddddddddddddddhhh",
          "_score" : 1.0,
          "_source":{"target_type": "timer",
                     "host_id": 2,
                     "job_id": 23,
                     "time_start": 405}
        }, {
          "_index" : "graphite_metrics2",
          "_type" : "metric",
          "_id" : "erwerwerwewtrewgfednvfngfngfrhfd",
          "_score" : 1.0,
          "_source":{"target_type": "timer",
                     "host_id": 3,
                     "job_id": 24,
                     "time_start": 4098}
        }, {
          "_index" : "graphite_metrics2",
          "_type" : "metric",
          "_id" : "dfherjgwetfrsupbretowegoegheorgsa",
          "_score" : 1.0,
          "_source":{"target_type": "timer",
                     "host_id": 22,
                     "job_id": 25,
                     "time_start": 4200}
        } ]
      }
    }

    """

    es = elasticsearch.Elasticsearch(host=host, port=port, timeout=timeout)
    if not es.indices.exists(index=index):
        return None
    return es.search(index=index, body=query)