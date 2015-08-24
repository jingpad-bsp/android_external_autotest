# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import histogram_parser

from autotest_lib.client.common_lib import error

def  verify(cr, histogram_name, histogram_bucket_value):
     """Verifies histogram availability and rate in a parsed histogram bucket

     @param cr: object, the Chrome instance
     @param histogram_name: string, name of the histogram
     @param histogram_bucket_value: int, refer to the bucket of the histogram
     """

     parser = histogram_parser.HistogramParser(cr, histogram_name)
     buckets = parser.buckets

     if (not buckets or
          histogram_bucket_value not in buckets or
          not buckets[histogram_bucket_value] or
          buckets[histogram_bucket_value].percent < 100.0):
          raise error.TestError('%s not found or not at 100 percent. %s'
              % (histogram_bucket_value, str(parser)))
