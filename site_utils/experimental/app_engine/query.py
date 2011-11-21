import logging
import os
import time

from google.appengine.dist import use_library
use_library('django', '1.2')

try:
  import json
except ImportError:
  from django.utils import simplejson as json

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import settings

from dash_db import Board, Build, Category, Netbook, Job, Test


class JobQuery(webapp.RequestHandler):
  def get(self):
    self.board_name = self.request.get('board', None)
    self.build_name = self.request.get('build', None)
    self.category_names = set(self.request.get('categories',
                              settings.DEFAULT_CATEGORIES).split(','))
    self.test_names = set(self.request.get('tests', '').split(','))

    self.response.headers['Content-Type'] = 'text/plain'

    if self.board_name is None:
      return self.ReturnNone()
    self.board = Board.get(self.board_name)
    if not self.board or not self.board.builds:
      return self.ReturnNone()
    if self.build_name is None:
      self.build_name = self.board.builds[0]
    self.build = Build.get(self.board_name, self.build_name)
    if not self.build:
      return self.ReturnNone()

    for category_name in self.category_names:
      category = Category.get(category_name)
      if category:
        self.test_names.update(category.test_names)

    jobs = []
    running_jobs = []
    aborted_jobs = []
    failed_jobs = []
    job_query = Job.all()
    job_query.filter('board = ', self.board_name)
    job_query.filter('build = ', self.build_name)
    # should be ordered by key
    job_query.order('-__key__')
    job_query.fetch(10000)
    for job in job_query:
      if job.job_name in self.category_names:
        jobs.append(job)
        if not job.completed:
          running_jobs.append(job)
        if job.aborted:
          aborted_jobs.append(job)
        if not job.job_status:
          logging.info(job.job_status)
          failed_jobs.append(job)

    # get all bad tests for this build.
    failed_tests = []
    job_ids = [job.id for job in jobs]
    test_query = Test.all()
    test_query.filter('board = ', self.board_name)
    test_query.filter('build = ', self.build_name)
    test_query.order('-test_finished_time')
    test_query.fetch(500)
    for test in test_query:
      if test.test_name in self.test_names:
        if test.status != 'GOOD' and test.job_id in job_ids:
          failed_tests.append(test)

    if running_jobs:
      return self.ReturnRunning(running_jobs)

    if not jobs:  # no job posted yet.
      return self.ReturnPending()

    return self.ReturnDone(aborted_jobs + failed_jobs, failed_tests)


  def ReturnNone(self):
    json_dict = {'status': 'None',
                 'desc': 'No board named %s or no build discovered for this '
                         'board.' % self.board_name}
    self.response.out.write(json.dumps(json_dict))

  
  def ReturnPending(self):
    json_dict = {'status': 'Pending',
                 'desc': 'Build %s is under testing in the lab.' %
                         self.build_name}
    self.response.out.write(json.dumps(json_dict))


  def ReturnRunning(self, running_jobs):
    job = running_jobs[0]
    json_dict = {'status': 'Running',
                 'job_id': job.id,
                 'job_url': 'http://cautotest/afe/#tab_id=view_job&object_id=%s' % job.id,
                 'desc': 'Tests are still running in the lab.'}
    self.response.out.write(json.dumps(json_dict))


  def ReturnDone(self, error_jobs, tests):
    summary_status = 'GOOD'
    category = ','.join(self.category_names)
    test_jsons = []
    for test in tests:
      if test.status != 'GOOD':
        status = 'Failed'
        test_json = {
          'test': test.test_name,
          'test_log': test.test_log_url
        }
        test_jsons.append(test_json)
        summary_status = 'Failed'
    json_dict = {'status': summary_status,
                 'board': self.board.name,
                 'build': self.build.name,
                 'failed_tests': test_jsons,
                 'desc': 'Tests finished in the lab.'}
    if error_jobs:
      json_dict['status'] = 'Failed'
      json_dict['job_id'] = error_jobs[-1].id
      json_dict['desc'] = 'Tests were failed due to some errors.'
    self.response.out.write(json.dumps(json_dict))


application = webapp.WSGIApplication([('/query', JobQuery),
                                      ],
                                      debug=False)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
