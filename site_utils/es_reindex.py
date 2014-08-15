# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file will copy all data from one index into another index.


"""This file will copy all data from one index into another index.

usage: es_reindex.py [-h] [--index_old INDEX_OLD] [--index_new INDEX_NEW]
                     [--timeout TIMEOUT] [--size SIZE]

optional arguments:
  -h, --help            show this help message and exit
  --index_old INDEX_OLD
  --index_new INDEX_NEW
  --timeout TIMEOUT     enter timeout
  --size SIZE           enter max entries to return

"""


import argparse

import common
from autotest_lib.client.common_lib.cros.graphite import es_utils


def main():
    """main script. """

    parser = argparse.ArgumentParser()
    parser.add_argument('--index_old', type=str, dest='index_old')
    parser.add_argument('--index_new', type=str, dest='index_new')
    parser.add_argument('--timeout', type=int, dest='timeout',
                        help='enter timeout', default=3)
    parser.add_argument('--size', type=int, dest='size',
                        help='enter max entries to return',
                        default=10000000)
    options = parser.parse_args()
    index_old, index_new = options.index_old, options.index_new
    host = es_utils.METADATA_ES_SERVER
    port = es_utils.ES_PORT
    timeout = options.timeout
    print 'Querying ES on %s:%s \n\n' % (host, port)
    print 'Moving from index: %s to index: %s' % (index_old, index_new)
    query = {
                'query' : {
                    'match_all' : {}
                },
                'size': options.size
            }
    host = es_utils.METADATA_ES_SERVER
    port = es_utils.ES_PORT
    print 'Querying ES on %s:%s \n\n' % (host, port)
    print query, index_old, host, port, '\n\n'
    result = es_utils.execute_query(query, index_old, host, port, timeout)
    print result['hits']['total']
    print 'created all the results :)'
    es = es_utils.ESMetadata()
    for hit in result['hits']['hits']:
        metadata = hit['_source']
        es.post(type_str=hit['_type'], metadata=metadata, index=index_new)
    print 'done'


if __name__ == '__main__':
    main()
