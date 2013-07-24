#!/usr/bin/python
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Tool to shrink autotest db by deleting old data.
"""
import datetime
import optparse
import os

settings = "autotest_lib.frontend.settings"
os.environ["DJANGO_SETTINGS_MODULE"] = settings

# For db access.
import common
from django.db import connection
from autotest_lib.frontend.afe import models as afe_models
from autotest_lib.frontend.tko import models as tko_models


class DBConnection(object):
  def __init__(self, dry_run, verbose):
    self.dry_run = dry_run
    self.verbose = verbose
    if not self.dry_run:
      self.cursor = connection.cursor()

  def execute(self, stmt):
    if self.verbose:
      print stmt
    if not self.dry_run:
      self.cursor.execute(stmt)

  def close(self):
    if not self.dry_run:
      self.cursor.close()


BATCH_SIZE = 1000


def delete_job(conn, afe_job):
  afe_host_queue_entry_ids = set([str(afe_host_queue_entry.id)
      for afe_host_queue_entry in afe_models.HostQueueEntry.objects.filter(
          job=afe_job)])
  if afe_host_queue_entry_ids:
    conn.execute('DELETE FROM afe_aborted_host_queue_entries WHERE '
                 'queue_entry_id in (%s);' % ','.join(afe_host_queue_entry_ids))
    conn.execute('DELETE FROM afe_special_tasks WHERE '
                 'queue_entry_id in (%s);' % ','.join(afe_host_queue_entry_ids))

  conn.execute('DELETE FROM afe_host_queue_entries WHERE job_id=%d;' %
               afe_job.id)
  conn.execute('DELETE FROM afe_ineligible_host_queues WHERE job_id=%d;' %
               afe_job.id)
  conn.execute('DELETE FROM afe_jobs_dependency_labels WHERE job_id=%d;' %
               afe_job.id)

  if afe_job.parameterized_job_id:
    conn.execute('DELETE FROM afe_parameterized_job_parameters '
                 'WHERE parameterized_job_id=%d;' %
                 afe_job.parameterized_job_id)
    conn.execute('DELETE FROM afe_parameterized_jobs WHERE id=%d;' %
                 afe_job.parameterized_job_id)

  tko_test_ids = set()
  tko_job_ids = set()
  for tko_test_view in tko_models.TestView.objects.filter(
      afe_job_id=afe_job.id):
    tko_test_ids.add(str(tko_test_view.test_idx))
    tko_job_ids.add(str(tko_test_view.job_idx))

  batches = len(tko_test_ids) / BATCH_SIZE + 1
  tko_test_ids = list(tko_test_ids)
  for i in range(batches):
    test_ids = tko_test_ids[i*BATCH_SIZE : (i+1)*BATCH_SIZE]
    conn.execute('DELETE FROM tko_iteration_result WHERE test_idx in (%s);' %
                 ','.join(test_ids))
    conn.execute('DELETE FROM tko_iteration_perf_value WHERE test_idx in '
                 '(%s);' % ','.join(test_ids))
    conn.execute('DELETE FROM tko_iteration_attributes WHERE test_idx in (%s);'
                 % ','.join(test_ids))
    conn.execute('DELETE FROM tko_test_attributes WHERE test_idx in (%s);' %
                 ','.join(test_ids))

  if tko_job_ids:
    conn.execute('DELETE FROM tko_tests WHERE job_idx in (%s);' %
                 ','.join(tko_job_ids))
    conn.execute('DELETE FROM tko_job_keyvals WHERE job_id in (%s);' %
                 ','.join(tko_job_ids))

  conn.execute('DELETE FROM tko_jobs WHERE afe_job_id=%d;' % afe_job.id)
  conn.execute('DELETE FROM afe_jobs WHERE id=%d;' % afe_job.id)



def main():
  parser = optparse.OptionParser()
  parser.add_option('--days', type='int', dest='days', default=180,
                    help='How many days of data we want to keep in the db.')
  parser.add_option('--dry_run', dest='dry_run', default=False,
                    action='store_true',
                    help='Where we like to apply the sql commands to db.')
  parser.add_option('--verbose', dest='verbose', default=False,
                    action='store_true',
                    help='Print out all sql statement.')

  options, _ = parser.parse_args()

  conn = DBConnection(options.dry_run, options.verbose)
  d = datetime.date.today()
  d = d - datetime.timedelta(days=options.days)
  for afe_job in afe_models.Job.objects.filter(created_on__lte=d):
    print 'Delete afe job %d.' % afe_job.id
    delete_job(conn, afe_job)

  print 'Optimize table after deletion.'
  conn.execute('OPTIMIZE TABLE afe_aborted_host_queue_entries;')
  conn.execute('OPTIMIZE TABLE afe_host_queue_entries;')
  conn.execute('OPTIMIZE TABLE afe_ineligible_host_queues;')
  conn.execute('OPTIMIZE TABLE afe_jobs_dependency_labels;')
  conn.execute('OPTIMIZE TABLE afe_parameterized_job_parameters;')
  conn.execute('OPTIMIZE TABLE afe_parameterized_jobs;')
  conn.execute('OPTIMIZE TABLE tko_iteration_result;')
  conn.execute('OPTIMIZE TABLE tko_iteration_perf_value;')
  conn.execute('OPTIMIZE TABLE tko_iteration_attributes;')
  conn.execute('OPTIMIZE TABLE tko_test_attributes;')
  conn.execute('OPTIMIZE TABLE tko_tests;')
  conn.execute('OPTIMIZE TABLE tko_jobs;')
  conn.execute('OPTIMIZE TABLE afe_jobs;')
  conn.close()


if __name__ == '__main__':
  main()
