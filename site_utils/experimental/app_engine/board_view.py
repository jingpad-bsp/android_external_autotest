import logging
import os
import time

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

import settings
import base_view
import utils

from dash_db import Build, NetbookBoard, Test, Category


def CategoryDetailTable(netbook, board, category, limit):
  header_height = settings.DEFAULT_TABLE_HEADER_HEIGHT
  tbl_header = []
  tbl_name = category.name

  test_dict = {}
  tested_tests = set()
  build_dict = {}
  for i in range(len(category.test_names)/settings.IN_QUERY_LIMIT + 1):
    category_names = category.test_names[i*settings.IN_QUERY_LIMIT:(i+1)*settings.IN_QUERY_LIMIT]
    test_query = Test.all()
    test_query.filter('netbook = ', netbook.name)
    test_query.filter('board = ', board.name)
    if category.is_job_name:
      test_query.filter('job_name = ', category.name)
    test_query.filter('test_name in ', category_names)
    test_query.order('-test_finished_time')
    results = test_query.fetch(limit * 30)
    for test in results:
      if test.build not in build_dict:
        build_dict[test.build] = Build.get(board.name, test.build)
      tests = test_dict.setdefault(test.build, {})
      tests[test.test_name] = test
      tested_tests.add(test.test_name)

  for test_name in sorted(tested_tests):
    link = '/test?test_name=%s' % test_name
    popup = ''
    title = test_name
    if test_name.split('_')[0] == category.name:
      test_name = test_name.split('_')[1]
    if len(test_name) > settings.DEFAULT_LENGTH:
      test_name = test_name[:settings.DEFAULT_LENGTH] + '...'
    header_name = test_name
    tbl_header.append(utils.Render('test_col_header.html', locals()))

  tbl_rows = []

  for build_name in board.builds[:limit]:
    build = build_dict.get(build_name, None)
    if not build:
      build = Build.get(board.name, build_name)
    cells = []
    build_link = '/build?board=%s&build=%s' % (board.name, build_name)
    started_time, finished_time, build_time = utils.FormatBuildTime(build)
    chrome_version = '%s(%s)' % (build.chrome_version, build.chrome_svn_number)
    build_popup = utils.Render('build_popup.html', locals())
    tested = False
    for test_name in sorted(tested_tests):
      test = test_dict.get(build_name, {}).get(test_name, None)
      if test:
        tested = True
      cells.append(utils.RenderTestCell(test))
    if tested:
      tbl_rows.append((build_name, build_link, build_popup, cells))

  if tbl_header and tbl_rows:
    return utils.Render('table.html', locals())
  else:
    return


class BoardView(base_view.BaseView):
  def do_get(self):
    self.board_bar()
    self.netbook_bar()

    netbook_board = NetbookBoard.get(self.netbook.name, self.board.name)
    if netbook_board.categories:
      category_link_list = []
      for category_name in netbook_board.categories:
        category_link_list.append(
            '<a href="?board=%s&netbook=%s&category=%s&limit=%d">%s</a>' %
            (self.board.name, self.netbook.name, category_name, self.limit, category_name))
    self.response.out.write('<div style="clear:both;">')
    self.response.out.write(' | '.join(category_link_list))
    self.response.out.write('</div>')
    self.spacer()

    # legend
    self.response.out.write(utils.Render('legend.html', locals()))
    self.spacer()

    table = CategoryDetailTable(self.netbook, self.board, self.category, self.limit)
    if table:
      self.response.out.write(table)
    self.timing()


application = webapp.WSGIApplication([('/board', BoardView),
                                     ],
                                     debug=False)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
