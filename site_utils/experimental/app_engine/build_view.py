import cStringIO
import logging
import os
import time

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

import settings
import base_view
import utils
from dash_db import Board, Build, Category, Job, Test


def BuildDetailTable(category_name, test_dict):
  tbl_name = category_name

  tbl_header = []
  netbooks = set()
  for tests in test_dict.values():
    netbooks = netbooks.union(tests.keys())
  netbooks = list(netbooks)
  netbooks.sort()

  for netbook in netbooks:
    header_name = netbook
    tbl_header.append(utils.Render('col_header.html', locals()))

  test_names = test_dict.keys()
  test_names.sort()

  tbl_rows = []
  for test_name in test_names:
    link = '/test?test_name=%s' % test_name
    test_label = test_name
    if test_label.split('_')[0] == category_name:
      test_label = test_name.split('_')[1]
    cells = []
    netbook_tested = False
    for netbook_name in netbooks:
      test = test_dict[test_name].get(netbook_name, None)
      cells.append(utils.RenderTestCell(test))
      if test:
        netbook_tested = True
    if netbook_tested:
      tbl_rows.append((test_label, link, '', cells))
  if tbl_header and tbl_rows:
    return utils.Render('table.html', locals())
  else:
    return


def BuildDetailTables(board_name, build_name):
  str_buf = cStringIO.StringIO()
  job_dict = {}
  test_dict = {}
  def add_test(category_name, netbook_name, test_name, test):
    tests = test_dict.setdefault(category_name, {})
    netbooks = tests.setdefault(test_name, {})
    netbooks[netbook_name] = test

  test_query = Test.all()
  test_query.filter('board = ', board_name)
  test_query.filter('build = ', build_name)
  test_query.fetch(limit=10000)

  for test in test_query:
    if test.job_id in job_dict:
      job = job_dict[test.job_id]
    else:
      job = Job.get(test.job_id)
      job_dict[test.job_id] = job
    category_names = utils.ParseCategories(job.job_name, test.test_name)
    for category_name in category_names:
      add_test(category_name, test.netbook, test.test_name, test)
    if test.status != 'GOOD':
      add_test('failure', test.netbook, test.test_name, test)

  if 'failure' in test_dict:
    table = BuildDetailTable('failure', test_dict['failure'])
    if table:
      str_buf.write('<div style="clear:both;">')
      str_buf.write(table)
      str_buf.write('</div>')
    del test_dict['failure']

  # sort the table by size:
  test_list = [(category_name, len(netbook_dict))
               for (category_name, netbook_dict) in test_dict.items()]
  def test_list_cmp(tuple1, tuple2):
    # a tuple here is a (string, int).
    if tuple1[1] == tuple2[1]:
      return cmp(tuple1[0], tuple2[0])
    else:
      return -cmp(tuple1[1], tuple2[1])
  test_list.sort(test_list_cmp)

  for category_name, _ in test_list:
    table = BuildDetailTable(category_name, test_dict[category_name])
    if table:
      # self.response.out.write('<div style="clear:both;">')
      str_buf.write('<div style="clear:none;float:left;padding-right:30px;">')
      str_buf.write(table)
      str_buf.write('</div>')

  return str_buf.getvalue()


class BuildView(base_view.BaseView):

  def parse_request(self):
    query_str = self.request.query_string
    board_name = self.request.get('board')

    self.board = Board.get(board_name)
    build_name = self.request.get('build', None)
    if not build_name:
      # get latest build
      build_name = self.board.builds[0]
    self.build = Build.get(board_name, build_name)
    if not self.build:
      raise

  def do_get(self):

    self.board_bar()

    index = self.board.builds.index(self.build.name)
    start = index - 2
    end = index + 3
    if start < 0:
      start = 0
    if end > len(self.board.builds):
      end = len(self.board.builds)

    self.response.out.write('<div style="clear:both;">')
    self.response.out.write('<b>Build</b>: ')
    next_build_links = []
    for idx in range(start, end):
      next_build_name = self.board.builds[idx]
      if idx == start and start != 0:
        link_name = '<<'
      elif idx == end - 1 and end != len(self.board.builds):
        link_name = '>>'
      else:
        link_name = next_build_name

      if next_build_name == self.build.name:
        next_build_links.append('<b>' + self.build.name + '</b>')
      else:
        next_build_links.append('<a href="?board=%s&build=%s">%s</a>' %
                                (self.board.name, next_build_name, link_name))
    self.response.out.write(' | '.join(next_build_links))
    self.response.out.write('</div>')

    # add link to build log and build image url.
    started_time, finished_time, build_time = utils.FormatBuildTime(self.build)
    test_started_time, test_finished_time, test_time = utils.FormatBuildTestTime(self.build)
    build_log_url = self.build.buildlog_url
    image_url = str(self.build.build_image_url)
    if image_url.endswith('image.zip'):
      image_dir = os.path.dirname(image_url)
    else:
      image_dir = image_url
    self.response.out.write(utils.Render('build.html', locals()))
    
    self.spacer()
    # legend
    self.response.out.write(utils.Render('legend.html', locals()))
    self.spacer()
    
    tables = BuildDetailTables(self.board.name, self.build.name)
    if tables:
      self.response.out.write(tables)
    self.timing()


application = webapp.WSGIApplication([('/build', BuildView),
                                     ],
                                     debug=False)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
