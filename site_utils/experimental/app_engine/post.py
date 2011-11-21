from google.appengine.dist import use_library
use_library('django', '1.2')

import base64
import logging
import os
import time

from google.appengine.ext import blobstore
from google.appengine.api import taskqueue
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import autotest_pb2
import security_token
import settings
import utils

from dash_db import Board, Build, Category, Job, JobPostTask, NetbookBoard
from dash_db import Test, TestName, TestPerfKey, TestHostKey


class BasePost(webapp.RequestHandler):
  def post(self):
    token = self.request.get('token')
    logging.info('Posted here. %s' % self.request.headers)
    if token != security_token.token():
      # token is not correct:
      return

    self.do_post()

  def do_post(self):
    raise


class BuildPost(BasePost):
  def get(self):
    # need to revisit.
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Boards: %d\n' % Board.all().count())
    for board in Board.all():
      self.response.out.write(board.name + ':' + str(len(board.builds)) + ' builds.\n')
    self.response.out.write('Builds: %d\n' % Build.all().count())


  def do_post(self):
    build_pb = autotest_pb2.Build()
    decoded_pb_str = base64.decodestring(self.request.get('payload'))
    build_pb.ParseFromString(decoded_pb_str)

    logging.debug(str(build_pb))

    instance = Build.create(build_pb.board, build_pb.name)
    instance.buildlog_json_url = build_pb.buildlog_json_url
    instance.buildlog_url = build_pb.buildlog_url
    instance.build_image_url = build_pb.build_image_url
    instance.build_started_time = build_pb.build_started_time
    instance.build_finished_time = build_pb.build_finished_time
    instance.chrome_version = build_pb.chrome_version
    instance.chrome_svn_number = build_pb.chrome_svn_number

    instance.put()


class JobPost(BasePost):
  def get(self):
    # need to revisit.
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Netbooks: %d\n' % Netbook.all().count(100))
    for netbook in Netbook.all():
      self.response.out.write(netbook.name + '\n')
    self.response.out.write('Boards: %d\n' % Board.all().count(100))
    for board in Board.all():
      self.response.out.write(board.name + ':' + str(len(board.builds)) + ' builds.\n')
      self.response.out.write(board.name + ':' + str(len(board.netbooks)) + ' netbooks.\n')
    self.response.out.write('Builds: %d\n' % Build.all().count(100))
    self.response.out.write('Jobs: %d\n' % Job.all().count(100))

  def do_post(self):
    job_task = JobPostTask()
    job_task.payload_pb = self.request.get('payload')
    job_task.put()
    taskqueue.add(queue_name='jobpost',
                  url='/_tasks/jobpost',
                  payload=str(job_task.key().id()))


class JobHandler(webapp.RequestHandler):
  def post(self):
    started_time = time.time()
    job_task = JobPostTask.get(int(self.request.body))
    job_pb = autotest_pb2.Job()
    decoded_pb_str = base64.decodestring(job_task.payload_pb)
    job_pb.ParseFromString(decoded_pb_str)

    logging.debug(str(job_pb))

    job = Job.create(job_pb.afe_job_id)

    job.job_name = job_pb.job_name
    job.owner = job_pb.owner

    job.build = job_pb.build
    job.board = job_pb.board
    job.netbook = job_pb.netbook

    board = Board.get(job_pb.board)
    if not board:
      board = Board.create(job_pb.board)
    board.add_build(job_pb.build)
    board.add_netbook(job_pb.netbook)
    board.put()

    job.job_created_time = float(job_pb.job_created_time)
    job.job_queued_time = float(job_pb.job_queued_time)
    job.job_started_time = float(job_pb.job_started_time)

    job.job_status = job_pb.job_status
    job.completed = job_pb.completed
    job.aborted = job_pb.aborted
    build = Build.get(job_pb.board, job_pb.build)
    if not build:
      build = Build.create(job_pb.board, job_pb.build)

    netbook_board = NetbookBoard.get(job_pb.netbook, job_pb.board)
    if not netbook_board:
      netbook_board = NetbookBoard.create(job_pb.netbook, job_pb.board)


    job.job_finished_time = float(job_pb.job_finished_time)
    job.passed = job_pb.passed
    job.total = job_pb.total
    categories = {}
    for test_pb in job_pb.tests:
      test = Test.create(test_pb.tko_test_id)
      test.job_id = test_pb.afe_job_id
      test.netbook = job.netbook
      test.board = job.board
      test.build = job.build
      test.owner = job_pb.owner
      test.test_name = test_pb.test_name
      test.job_name = job.job_name
      test.hostname = test_pb.hostname
      test.status = test_pb.status
      test.test_log_url = test_pb.test_log_url
      test.test_started_time = test_pb.test_started_time
      test.test_finished_time = test_pb.test_finished_time

      if test.status != 'GOOD':
        test.reason = test_pb.reason

      if build.test_started_time is None or \
          build.test_started_time > test_pb.test_started_time:
        build.test_started_time = test_pb.test_started_time

      if build.test_finished_time is None or \
          build.test_finished_time < test_pb.test_finished_time:
        build.test_finished_time = test_pb.test_finished_time
      test.put()

      for host_keyval in test_pb.host_keyvals:
         test_host_key = TestHostKey.create(test_pb.tko_test_id, host_keyval.key)
         test_host_key.test_name = test_pb.test_name
         test_host_key.hostkey_value = host_keyval.value[:500]
         test_host_key.put()

      for perfkey_values in test_pb.perfkeys:
        perfkey = TestPerfKey.create(test_pb.tko_test_id, perfkey_values.key)
        perfkey.test_name = test_pb.test_name
        for value in perfkey_values.values:
          perfkey.add_value(value)
        perfkey.put()

      for category_name in utils.ParseCategories(job_pb.job_name,
                                                 test_pb.test_name):
        category = categories.get(category_name, None)
        if not category:
          category = Category.get(category_name)
          if not category:
            category = Category.create(category_name)
            category.is_job_name = category_name in settings.EXTRA_CATEGORIES
          categories[category_name] = category
        category.add_test(test_pb.test_name)

      test_name = TestName.create(test_pb.test_name)
      test_name.put()

    for category in categories.values():
      category.put()
      netbook_board.add_category(category.name)
    netbook_board.put()
    build.put()
    job.put()
    job_task.delete()

    email_alert = bool(self.request.get('email_alert', True))
    if email_alert:
      # TODO
      logging.info('At the end sending out email alert based on email config.')

    logging.info('job post task (%d) %d takes %d seconds.' %
                (int(self.request.body), job_pb.afe_job_id, 
                 time.time() - started_time))
    return


application = webapp.WSGIApplication([('/post/build', BuildPost),
                                      ('/post/job', JobPost),
                                      ('/_tasks/jobpost', JobHandler),
                                     ],
                                     debug=False)


def main():
  run_wsgi_app(application)


if __name__ == "__main__":
  main()
