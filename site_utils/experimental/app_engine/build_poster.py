#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'ericli@chromium.org (Eric Li)'


import logging
import optparse
import sys
import time

import common
from autotest_lib.utils.dashboard.build_info import BuildInfo

import autotest_pb2
import base_poster


def load_build(board_name, build_name, image_url):
  build = autotest_pb2.Build()

  build.board = board_name
  build.name = build_name
  tokens = build_name.split('-')
  build.version = tokens[0]
  build.hash = tokens[1][1:]
  build.seq = int(tokens[2][1:])

  build_info = BuildInfo()
  build.buildlog_json_url = build_info.GetBotURL(board_name, build_name, 
                                                 json_sub='json/')
  build.buildlog_url = build_info.GetBotURL(board_name, build_name)
  build.build_image_url = image_url
  build.build_started_time = build_info.GetStartedTime(board_name,
                             build_name)
  build.build_finished_time = build_info.GetFinishedTime(board_name,
                                                         build_name)
  if build.build_finished_time == 0.0:
    logging.warning('Could not find build log for %s %s' % (board_name,
                                                            build_name))
    build.build_finished_time = time.time()   # now
  if build_info.GetChromeVersion(board_name, build_name):
    build.chrome_version = build_info.GetChromeVersion(board_name,
                                                       build_name)[0]
    build.chrome_svn_number = int(build_info.GetChromeVersion(board_name,
                                                              build_name)[1])
  else:
    logging.warning('Could not figure out chrome version for (%s, %s) '
                    'from: %s' % (board_name, build_name, build.buildlog_url))
  build.build_time = build.build_finished_time - build.build_started_time
  return build


class BuildPoster(base_poster.BasePoster):
  def __init__(self, url, build):
    base_poster.BasePoster.__init__(self, url, build)
    self.logging_msg = 'Posted build info %s, %s.' % (build.board, build.name)

  def get_type(self):
    return 'build'


def setup_options(parser):
  base_poster.setup_options(parser)
  parser.add_option('--board', action='store', type='string',
                    dest='board', help='Board name.')
  parser.add_option('--build', action='store', type='string',
                    dest='build', help='Build version string.')
  parser.add_option('--image_url', action='store', type='string',
                    dest='image_url', help='Build version string.',
                    default='http://goto/chromeos-images')


def main():
  parser = optparse.OptionParser(usage='%prog [options]')
  setup_options(parser)
  options, _ = parser.parse_args()
  build = load_build(options.board, options.build, options.image_url)
  if build:
    poster = BuildPoster(options.url, build)
    logging.info('\n' + str(build))
    return poster.post()
  return -1

if __name__ == '__main__':
  sys.exit(main())
