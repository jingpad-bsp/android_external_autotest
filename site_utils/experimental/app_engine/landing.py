from google.appengine.dist import use_library
use_library('django', '1.2')

import logging
import os
import time

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

import base_view
import settings
import utils

from dash_db import Board, Build, Job


def BvtSummaryTable(board, limit):
  tbl_name = board.name
  header_name = 'Test End'
  tbl_header = [utils.Render('col_header.html', locals())]

  job_query = Job.all()
  job_query.filter('board = ', board.name)
  job_query.filter('job_name = ', 'bvt')
  job_query.order('-job_finished_time')
  results = job_query.fetch(limit*2)

  netbooks = set()

  job_dict = {}
  for job in results:
    netbooks.add(job.netbook)
    row = job_dict.setdefault(job.build, {})
    row[job.netbook] = job

  netbooks = list(netbooks)
  netbooks.sort()
  if netbooks:
    for netbook_name in netbooks:
      tbl_header.append(utils.Render('summary_table_col_header.html', locals()))
  else:
    return

  tbl_rows = []
  for build_name in board.builds[:limit]:
    finished_time = 0
    cells = []
    for netbook_name in netbooks:
      job = job_dict.get(build_name, {}).get(netbook_name, None)
      test_status = 'None'
      test_link = ''
      bg_color = settings.COLOR_GRAY
      if job:
        finished_time = max(finished_time, job.job_finished_time)

        if job.completed:
          test_status = '%s/%s' % (job.passed, job.total)
          test_link = '/board?board=%s&netbook=%s' % (board.name, netbook_name)
          if job.total and job.total == job.passed:
            bg_color = settings.COLOR_GREEN
          else:
            bg_color = settings.COLOR_RED
          if job.aborted:
            bg_color = settings.COLOR_ORANGE
        elif job.aborted:
          test_status = 'Aborted'
          test_link = 'http://cautotest/afe/#tab_id=view_job&object_id=%d' % job.id
          bg_color = settings.COLOR_ORANGE
        else:
          test_status = 'Testing'
          # job link should be to cautotest job page.
          test_link = 'http://cautotest/afe/#tab_id=view_job&object_id=%d' % job.id
      cells.append((test_status, test_link, '', bg_color))
    if finished_time:
      finished_time = time.strftime('%a %m/%d %H:%M',
          time.localtime(finished_time - settings.TIMEZONE_OFFSET))
    else:
      finished_time = 'Unknown'
    cells.insert(0, (finished_time, '', '', settings.COLOR_GRAY))

    build = Build.get(board.name, build_name)
    started_time, finished_time, build_time = utils.FormatBuildTime(build)
    chrome_version = build.get_chrome_version()
    build_link = 'build?board=%s&build=%s' % (board.name, build_name)
    build_popup = utils.Render('build_popup.html', locals())
    tbl_rows.append((build_name, build_link, build_popup, cells))
  if tbl_header and tbl_rows:
    return utils.Render('table.html', locals())


class LandingView(base_view.BaseView):
  def get(self):
    self.header()

    board_names = self.request.get('boards',
                                   settings.DEFAULT_BOARD_ORDER).split(',')
    limit = int(self.request.get('limit', settings.DEFAULT_TABLE_ROWS))

    for board_name in board_names:
      board = Board.get(board_name)
      if board:
        table = BvtSummaryTable(board, limit)
        if table:
          self.response.out.write('<div style="clear:none;float:left;padding-right:30px;">')
          self.response.out.write(table)
          self.response.out.write('</div>')
    self.timing()
    return


application = webapp.WSGIApplication([('/', LandingView),
                                      ],
                                      debug=False)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
