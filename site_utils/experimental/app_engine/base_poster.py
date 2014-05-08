#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'ericli@chromium.org (Eric Li)'


import base64
import logging
import urllib

import security_token


def setup_options(parser):
  logger = logging.getLogger()
  fmt = '%(levelname)s:%(message)s'
  dbg_fmt = '%(process)d:'
  cf = logging.Formatter(dbg_fmt + fmt)
  c = logging.StreamHandler()
  c.setFormatter(cf)
  logger.addHandler(c)
  logger.setLevel(logging.INFO)
  parser.add_option('-u', '--url', action='store', type='string',
                    dest='url', help='dashboard url.',
                    default='http://localhost:8080')


class BasePoster(object):
  def __init__(self, url, payload):
    self.url = url
    self.payload = payload
    self.data = {}
    self.logging_msg = None

  def get_type(self):
    raise

  def post(self):
    self.data['token'] = security_token.token()
    self.data['payload'] = base64.encodestring(self.payload.SerializeToString())
    try:
      response = urllib.urlopen(self.url + '/post/' + self.get_type(),
                                urllib.urlencode(self.data))
      logging.info(self.logging_msg)
      logging.info(response.getcode())
      
    except IOError, ioex:
      if ioex.errno == 'socket error':
        logging.warning('Remote server is not available')
        return -1
    return 0
