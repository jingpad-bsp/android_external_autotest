#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'ericli@chromium.org (Eric Li)'

import optparse
import os
import sys

settings = "autotest_lib.frontend.settings"
os.environ["DJANGO_SETTINGS_MODULE"] = settings

import common
from autotest_lib.frontend.afe import models as afe_models

import base_poster
import job_poster
import build_poster

builds = {}
def post_job_and_build(url, job_id):
  global builds
  job = job_poster.load_job(job_id)
  if job and job.owner == 'chromeos-test':
    cros_build = builds.get((job.board, job.build), None)
    if not cros_build:
      cros_build = build_poster.load_build(job.board, job.build, 'http://goto/chromeos-images')
      if cros_build:
        poster = build_poster.BuildPoster(url, cros_build)
        poster.post()
      builds[(job.board, job.build)] = cros_build
    poster = job_poster.JobPoster(url, job)
    poster.post()
  return -1


def main():
  parser = optparse.OptionParser(usage='%prog [options]')
  base_poster.setup_options(parser)
  options, _ = parser.parse_args()

  # 27000 ~ 29000
  for afe_job in afe_models.Job.objects.filter(
      owner='chromeos-test').order_by('-id')[:3000]:
    post_job_and_build(options.url, afe_job.id)
    import time
    time.sleep(1)


if __name__ == '__main__':
  sys.exit(main())
