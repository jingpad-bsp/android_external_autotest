#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'ericli@chromium.org (Eric Li)'


import logging
import os
import optparse
import re
import sys
import time

settings = "autotest_lib.frontend.settings"
os.environ["DJANGO_SETTINGS_MODULE"] = settings

import common
from autotest_lib.frontend.afe import models as afe_models
from autotest_lib.frontend.tko import models as tko_models

import autotest_pb2
import base_poster


JOBNAME_PARSER = re.compile('([\w-]*)-([\d]*\.[\d]*\.[\d]*\.[\d]*-r[\w]{8}-'
                            'b[\d]*)_([\w_]*)')


def datetime_to_float(datetime):
  if datetime:
    return time.mktime(datetime.timetuple())
  else:
    return 0.0


def load_job(job_id):
  try:
    afe_job = afe_models.Job.objects.get(id=job_id)
  except:
    logging.warning('afe_job %d does not exist in db.' % job_id)
    return

  try:
    m = re.match(JOBNAME_PARSER, afe_job.name)
    board = m.group(1)
    build = m.group(2)
    job_name = m.group(3)
  except:
    logging.warning('afe job: %d, %s does not match the name patter, skip.' %
                    (job_id, afe_job.name))
    return

  job_pb = autotest_pb2.Job()
  job_pb.afe_job_id = afe_job.id
  job_pb.job_name = job_name
  job_pb.board = board
  job_pb.build = build
  job_pb.owner = afe_job.owner
  if job_pb.owner != 'chromeos-test':
    return
  job_pb.job_created_time = datetime_to_float(afe_job.created_on)

  job_pb.aborted = False

  for host_queue_entry in afe_models.HostQueueEntry.objects.filter(job=afe_job):
    job_pb.aborted |= host_queue_entry.aborted
    netbook = host_queue_entry.meta_host.name
    if netbook == 'netbook_MARIO_MP':
      netbook = 'netbook_CR_48'
    if netbook.startswith('netbook_'):
      netbook = netbook[8:]
    if not job_pb.netbook:
      job_pb.netbook = netbook
    else:
      assert job_pb.netbook == netbook, \
        'Job %d was scheduled on more than one platforms' % job_id
  assert job_pb.netbook, 'Job %d was scheduled on None platform' % job_id

  for tko_job in tko_models.Job.objects.filter(afe_job_id=job_id):
    started_time = datetime_to_float(tko_job.started_time)
    if job_pb.job_started_time == 0.0  or \
        job_pb.job_started_time > started_time:
      job_pb.job_started_time = started_time
    finished_time = datetime_to_float(tko_job.finished_time)
    if job_pb.job_finished_time < finished_time:
      job_pb.job_finished_time = finished_time
    queued_time = datetime_to_float(tko_job.queued_time)
    if (job_pb.job_queued_time == 0.0 or
        job_pb.job_queued_time < queued_time):
      job_pb.job_queued_time = queued_time

  if not job_pb.job_finished_time:
    logging.info('job %d is not finished yet.', job_id)
    job_pb.completed = False
  else:
    job_pb.completed = True

  job_pb.job_status = True
  for test_view in tko_models.TestView.objects.filter(afe_job_id=job_id):
    if (test_view.test_name.startswith('CLIENT_JOB') or
        test_view.test_name.startswith('boot.')):
      continue
    if test_view.test_name == 'SERVER_JOB' or \
       test_view.test_name.startswith('reboot'):
      job_pb.job_status &= (test_view.status == 'GOOD') 
      continue

    job_pb.total += 1
    if test_view.status == 'GOOD':
      job_pb.passed += 1

    job_pb.job_status &= (test_view.status == 'GOOD')
    test_started_time = datetime_to_float(test_view.test_started_time)
    test_finished_time = datetime_to_float(test_view.test_finished_time)
    if job_pb.test_started_time == 0.0 or \
        job_pb.test_started_time > test_started_time:
      job_pb.test_started_time = test_started_time
    if job_pb.test_finished_time < test_finished_time:
      job_pb.test_finished_time = test_finished_time

    test_pb = job_pb.tests.add()
    test_pb.afe_job_id = test_view.afe_job_id
    test_pb.tko_test_id = test_view.test_idx

    test_pb.hostname = test_view.hostname
    test_pb.test_name = test_view.test_name
    test_pb.status = test_view.status
    test_pb.test_started_time = datetime_to_float(test_view.test_started_time)
    test_pb.test_finished_time = datetime_to_float(test_view.test_finished_time)

    if test_view.status == 'GOOD':
      suffix = 'DEBUG'
    else:
      suffix = 'ERROR'
      test_pb.reason = test_view.reason
    test_pb.test_log_url = ('results/%s/%s/debug/%s.%s' %  (test_view.job_tag,
        test_view.test_name, test_view.test_name, suffix))
    # we may override test_log_url for BrowserTest in the future.

    test = tko_models.Test.objects.get(test_idx=test_view.test_idx)
    for test_attribute in tko_models.TestAttribute.objects.filter(test=test):
      host_keyval = test_pb.host_keyvals.add()
      host_keyval.key = test_attribute.attribute
      host_keyval.value = test_attribute.value

    # perf
    for test_iteration_result in tko_models.IterationResult.objects.filter(
        test=test):
      found = False
      for perfkey_values in test_pb.perfkeys:
        if perfkey_values.key == test_iteration_result.attribute:
          perfkey_values.values.append(test_iteration_result.value)
          found = True
          break
      if not found:
        perfkey_values = test_pb.perfkeys.add()
        perfkey_values.key = test_iteration_result.attribute
        perfkey_values.values.append(test_iteration_result.value)
  return job_pb


class JobPoster(base_poster.BasePoster):
  def __init__(self, url, job):
    base_poster.BasePoster.__init__(self, url, job)
    self.data['email_alert'] = 0
    self.data['id'] = job.afe_job_id
    if job.job_finished_time:
      self.logging_msg = 'Posted job result %d, %s.' % (job.afe_job_id,
                                                        job.job_name)
    else:
      self.logging_msg = 'Posted running job %d, %s.' % (job.afe_job_id,
                                                         job.job_name)

  def get_type(self):
    return 'job'


def setup_options(parser):
  base_poster.setup_options(parser)
  parser.add_option('-j', '--job_id', action='store', type='int',
                    dest='job_id', help='afe_job_id to be posted.')


def main():
  parser = optparse.OptionParser(usage='%prog [options]')
  setup_options(parser)
  options, _ = parser.parse_args()
  job = load_job(options.job_id)
  if job:
    poster = JobPoster(options.url, job)
    return poster.post()
  return -1


if __name__ == '__main__':
  sys.exit(main())
