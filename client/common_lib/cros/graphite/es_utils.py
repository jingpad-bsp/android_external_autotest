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

import common

try:
    import elasticsearch
except ImportError:
    logging.debug('import elasticsearch failed,'
                  'no metadata will be reported.')
    import elasticsearch_mock as elasticsearch

from autotest_lib.client.common_lib import global_config


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

# For metadata reported along with stats in stats.py
INDEX_STATS_METADATA = '%s_stats_metadata' % (
        global_config.global_config.get_config_value(
                'SERVER', 'hostname', type=str, default='localhost'))


def create_udp_message_from_metadata(index, metadata):
    """Outputs a json encoded string to send via udp to es server.

    @param index: index in elasticsearch to insert data to
    @param metadata: dictionary object containing metadata
    @returns: string representing udp message.

    Format of the string follows bulk udp api for es.
    """
    metadata_message = json.dumps(metadata, separators=(', ', ' : '))
    message_header = json.dumps(
            {'index': {'_index': index, '_type': 'metadata'}},
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


    def send_data(self, index, metadata, use_http):
        """Sends data to insert into elasticsearch.

        @param index: index in elasticsearch to insert data to.
        @param metadata: dictionary object containing metadata
        @param use_http: whether to use http. udp is very little overhead
          (around 3 ms) compared to using http (tcp) takes ~ 500 ms
          for the first connection and 50-100ms for subsequent connections.
        """
        if not use_http:
            try:
                message = create_udp_message_from_metadata(index, metadata)
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                result = sock.sendto(message, (self.host, ES_UDP_PORT))
            except socket.error as e:
                logging.warn(e)
        else:
            self.es = elasticsearch.Elasticsearch(host=self.host,
                                                  port=self.port,
                                                  timeout=self.timeout)
            self.es.index(index=index, doc_type='metadata', body=metadata)


    def post(self, index, metadata=None, use_http=ES_USE_HTTP, **kwargs):
        """Wraps call of send_data, inserts entry into elasticsearch.

        @param index: index in elasticsearch to insert data to.
        @param metadata: dictionary object containing metadata
        @param use_http: will use udp to send data when this is False.
        @param kwargs: additional metadata fields
        """
        if not metadata:
            return
        # Create a copy to avoid issues from mutable types.
        metadata_copy = metadata.copy()
        # kwargs could be extra metadata, append to metadata.
        metadata_copy.update(kwargs)
        try:
            self.send_data(index, metadata_copy, use_http)
        except elasticsearch.ElasticsearchException as e:
            logging.error(e)