# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file defines helper functions for putting entries into elasticsearch.

"""Utils for sending metadata to elasticsearch

Elasticsearch is a key-value store NOSQL database.
Source is here: https://github.com/elasticsearch/elasticsearch
We will be using es to store our metadata.

For example, if we wanted to store the following metadata:

metadata = {
    'host_id': 1
    'job_id': 20
    'time_start': 100000
    'time_recorded': 100006
}

The following call will send metadata to the default es server.
    es_utils.ESMetadata().post(index, metadata)
We can also specify which port and host to use.

Using for testing: Sometimes, when we choose a single index
to put entries into, we want to clear that index of all
entries before running our tests. Use clear_index function.
(see es_utils_functionaltest.py for an example)

This file also contains methods for sending queries to es. Currently,
the query (json dict) we send to es is quite complicated (but flexible).
We've included several methods that composes queries that would be useful.
These methods are all named create_*_query()

For example, the below query returns job_id, host_id, and job_start
for all job_ids in [0, 99999] and host_id matching 10.

range_eq_query = {
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

To send a query once it is created, call execute_query() to send it to the
intended elasticsearch server.

"""

import json
import logging
import socket
import time

import common

try:
    import elasticsearch
except ImportError:
    import elasticsearch_mock as elasticsearch

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import time_utils


# Server and ports for elasticsearch (for metadata use only)
METADATA_ES_SERVER = global_config.global_config.get_config_value(
        'CROS', 'ES_HOST', default='localhost')
ES_PORT = global_config.global_config.get_config_value(
        'CROS', 'ES_PORT', type=int, default=9200)
ES_UDP_PORT = global_config.global_config.get_config_value(
        'CROS', 'ES_UDP_PORT', type=int, default=9700)
ES_DEFAULT_INDEX = global_config.global_config.get_config_value(
        'CROS', 'ES_DEFAULT_INDEX', default='default')
ES_USE_HTTP = global_config.global_config.get_config_value(
        'CROS', 'ES_USE_HTTP', type=bool, default=False)

# 3 Seconds before connection to esdb timeout.
DEFAULT_TIMEOUT = 3

# If CLIENT/metadata_index is not set, INDEX_METADATA falls back to autotest
# instance name (SERVER/hostname).
INDEX_METADATA = global_config.global_config.get_config_value(
        'CLIENT', 'metadata_index', type=str, default=None)
if not INDEX_METADATA:
    INDEX_METADATA = global_config.global_config.get_config_value(
            'SERVER', 'hostname', type=str, default='localhost')


class EsUtilException(Exception):
    """Exception raised when functions here fail. """
    pass

def create_udp_message_from_metadata(index, type_str, metadata):
    """Outputs a json encoded string to send via udp to es server.

    @param index: index in elasticsearch to insert data to
    @param type_str: sets the _type field in elasticsearch db.
    @param metadata: dictionary object containing metadata
    @returns: string representing udp message.

    Format of the string follows bulk udp api for es.
    """
    metadata_message = json.dumps(metadata, separators=(', ', ' : '))
    message_header = json.dumps(
            {'index': {'_index': index, '_type': type_str}},
            separators=(', ', ' : '))
    # Add new line, then the metadata message, then another new line.
    return '%s\n%s\n' % (message_header, metadata_message)


class ESMetadata(object):
    """Class handling es connection for posting metadata. """

    def __init__(self, host=METADATA_ES_SERVER, port=ES_PORT,
                 timeout=DEFAULT_TIMEOUT):
        """Initialize ESMetadata object.

        @param host: elasticsearch host
        @param port: elasticsearch port
        @param timeout: how long to wait while connecting to es.
        """
        self.host = host
        self.port = port
        self.timeout = timeout


    def _send_data(self, type_str, index, metadata, use_http):
        """Sends data to insert into elasticsearch.

        @param type_str: sets the _type field in elasticsearch db.
        @param index: index in elasticsearch to insert data to.
        @param metadata: dictionary object containing metadata
        @param use_http: whether to use http. udp is very little overhead
          (around 3 ms) compared to using http (tcp) takes ~ 500 ms
          for the first connection and 50-100ms for subsequent connections.
        """
        if not use_http:
            try:
                message = create_udp_message_from_metadata(index, type_str,
                                                           metadata)
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                result = sock.sendto(message, (self.host, ES_UDP_PORT))
            except socket.error as e:
                logging.warn(e)
        else:
            self.es = elasticsearch.Elasticsearch(host=self.host,
                                                  port=self.port,
                                                  timeout=self.timeout)
            self.es.index(index=index, doc_type=type_str, body=metadata)


    def post(self, type_str, metadata=None, index=INDEX_METADATA,
             use_http=ES_USE_HTTP, log_time_recorded=True, **kwargs):
        """Wraps call of send_data, inserts entry into elasticsearch.

        @param type_str: sets the _type field in elasticsearch db.
        @param index: index in elasticsearch to insert data to.
        @param metadata: dictionary object containing metadata
        @param use_http: will use udp to send data when this is False.
        @param log_time_recorded: True to automatically save the time metadata
                                  is recorded. Default is True.
        @param kwargs: additional metadata fields
        """
        if not metadata:
            return
        # Create a copy to avoid issues from mutable types.
        metadata_copy = metadata.copy()
        # kwargs could be extra metadata, append to metadata.
        metadata_copy.update(kwargs)
        # metadata should not contain anything with key '_type'
        if '_type' in metadata_copy:
            type_str = metadata_copy['_type']
            del metadata_copy['_type']
        if log_time_recorded:
            metadata_copy['time_recorded'] = time.time()
        try:
            self._send_data(type_str, index, metadata_copy, use_http)
        except elasticsearch.ElasticsearchException as e:
            logging.error(e)


def create_range_eq_query_multiple(equality_constraints,
                                   fields_returned=None,
                                   range_constraints=[],
                                   size=None,
                                   sort_specs=None,
                                   regex_constraints=[]):
    """Creates a dict. representing multple range and/or equality queries.

    Example input:
        create_range_eq_query_multiple(
                fields_returned = ['time_recorded', 'hostname',
                                   'status', 'dbg_str'],
                equality_constraints = [
                    ('_type', 'host_history'),
                    ('hostname', '172.22.169.106'),
                ],
                range_constraints = [
                    ('time_recorded', 1405628341.904379, 1405700341.904379)
                ],
                size=20,
                sort_specs=[
                    'hostname',
                    {'time_recorded': 'asc'},
                ]
        )

    Output:
    {
        'fields': ['time_recorded', 'hostname', 'status', 'dbg_str'],
        'query': {
            'bool': {
                'minimum_should_match': 3,
                'should': [
                    {
                        'term':  {
                            '_type': 'host_history'
                        }
                    },

                    {
                        'term': {
                            'hostname': '172.22.169.106'
                        }
                    },

                    {
                        'range': {
                            'time_recorded': {
                                'gte': 1405628341.904379,
                                'lte': 1405700341.904379
                            }
                        }
                    }
                ]
            },
        },
        'size': 20
        'sort': [
            'hostname',
            { 'time_recorded': 'asc'},
        ]
    }

    @param fields_returned: list of fields that we should return when
                            the query is executed. Set it to None to return all
                            fields. Note that the key/vals will be stored in
                            _source key of the hit object, if fields_returned is
                            set to None.
    @param equality_constraints: list of tuples of (field, value) pairs
        representing what each field should equal to in the query.
        e.g. [ ('field1', 1), ('field2', 'value') ]
    @param range_constraints: list of tuples of (field, low, high) pairs
        representing what each field should be between (inclusive).
        e.g. [ ('field1', 2, 10), ('field2', -1, 20) ]
        If you want one side to be unbounded, you can use None.
        e.g. [ ('field1', 2, None) ] means value of field1 >= 2.
    @param size: max number of entries to return.
    @param sort_specs: A list of fields to sort on, tiebreakers will be
        broken by the next field(s).
    @param regex_constraints: A list of regex constraints of tuples of
        (field, value) pairs, e.g., [('filed1', '.*value.*')].

    @param returns: dictionary object that represents query to es.
                    This will return None if there are no equality constraints
                    and no range constraints.
    """
    if not equality_constraints and not range_constraints:
        raise EsUtilException('No range or equality constraints specified...')

    # Creates list of range dictionaries to put in the 'should' list.
    range_list = []
    if range_constraints:
        for key, low, high in range_constraints:
            if low is None and high is None:
                continue
            temp_dict = {}
            if low is not None:
                temp_dict['gte'] = time_utils.to_epoch_time(low)
            if high is not None:
                temp_dict['lte'] = time_utils.to_epoch_time(high)
            range_list.append( {'range': {key: temp_dict}})

    # Creates the list of term dictionaries to put in the 'should' list.
    eq_list = [{'term': {k: v}} for k, v in equality_constraints if k]
    regex_list = [{'regexp': {k: v}} for k, v in regex_constraints if k]
    num_constraints = (len(equality_constraints) + len(range_constraints) +
                       len(regex_list))
    query = {
             'query': {
                       'bool': {
                                'should': eq_list + range_list + regex_list,
                                'minimum_should_match': num_constraints,
                               }
                      },
            }
    if fields_returned:
        query['fields'] = fields_returned
    if size:
        query['size'] = size
    if sort_specs:
        query['sort'] = sort_specs
    return query


def execute_query(query, index=INDEX_METADATA, host=METADATA_ES_SERVER,
                  port=ES_PORT, timeout=3):
    """Makes a query on the given index.

    @param query: query dictionary (see create_range_query)
    @param index: index within db to query, default to setting
                  CLIENT/metadata_index.
    @param host: host running es, default to setting CROS/ES_HOST.
    @param port: port running es, default to setting CROS/ES_PORT.
    @param timeout: seconds to wait before es retries if conn. fails.
                    default is 3 seconds.
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


def convert_hit(hit):
    """Convert ES query hits _source value to fields data.

    When query ES without specifying fields value, the return hits retrieve all
    data of the record and stores under `_source` key. Following is an example
    of the _source value:
    {'hostname': 'dut1', 'time_recorded': 17820784, 'status': 'Ready'}
    On the other hand, if a query specifies fields value, the return hits
    retrieve data only for given fields, for example:
    {'hostname': ['dut1'], 'time_recorded': [17820784], 'status': ['Ready']}
    Note that, althought the result look the same, the second case has value
    stored in a list. To make the data consistent and easy to process, this
    function convert the list value to a single data if applicable.

    @param hit: ES query hit.
    @return: A dictionary of cleaned up key, values.
    """
    if not hit:
        return None
    cleaned_data = {}
    for field,value in hit.items():
        cleaned_data[field] = (value[0] if isinstance(value, list) and
                               len(value)==1 else value)
    return cleaned_data


def get_metadata(record, excluded_fields):
    """Get the metadata from an ES record excluding a given list of fields.

    @param record: A dictionary from ES query result, e.g.,
                   {'hostname': ['123.3.4.5'],
                    'time_recorded': [1782038784],
                    'status': ['Repairing'],
                    'task_id': [4574],
                    'task_name': ['Repair']}
    @param excluded_fields: A list of fields to be excluded from the record.
    @returns: A dictionary of ES query result excluding a given list of fields.
    """
    result = {}
    including_fields = set(record.keys()) - set(excluded_fields)
    for field in including_fields:
        result[field] = record[field]
    return result
