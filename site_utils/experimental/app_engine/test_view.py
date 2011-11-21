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
from dash_db import Board, Build, Category, Netbook, Job
from dash_db import Test, TestName

def TestDetailTable(board, test_list, limit):
  test_dict = {}
  for test in test_list:
    tests = test_dict.setdefault(test.netbook, {})
    tests.setdefault(test.build, test)

  tbl_name = board.name
  header_height = 30
  tbl_header = []
  netbooks = test_dict.keys()
  netbooks.sort()
  for header_name in netbooks:
    tbl_header.append(utils.Render('col_header.html', locals()))

  tbl_rows = []
  netbook_tested = {}
  netbooks = test_dict.keys()
  netbooks.sort()

  count = 0
  for build_name in board.builds:
    build = Build.get(board.name, build_name)
    cells = []
    chrome_version = build.get_chrome_version()
    started_time, finished_time, build_time = utils.FormatBuildTime(build)
    build_popup = utils.Render('build_popup.html', locals())
    build_link = '/build?board=%s&build=%s' % (board.name, build_name)
    build_tested = False
    for netbook_name in netbooks:
      test = test_dict.get(netbook_name, None).get(build_name, None)
      if test:
        cells.append(utils.RenderTestCell(test, short=False))
        build_tested = True
        netbook_tested[netbook_name] = True
      else:
        cells.append(utils.RenderTestCell(None, short=False))
    if build_tested:
      count += 1
      tbl_rows.append((build_name, build_link, build_popup, cells))
    if count >= limit:
      break

  if tbl_header and tbl_rows:
    return utils.Render('table.html', locals())
  else:
    return


class TestView(base_view.BaseView):
  def get(self):
    self.header()
    self.limit = int(self.request.get('limit', settings.DEFAULT_TABLE_ROWS))
    self.boards = self.request.get('boards', settings.DEFAULT_BOARD_ORDER)

    test_name = self.request.get('test_name', '')
    self.response.out.write(utils.Render('test_search.html', locals()))
    if not test_name:
      return

    all_test_names = set([t.name for t in TestName.all()])
    if test_name in all_test_names:
      filtered_test_names = [test_name]
    else:
      filtered_test_names = [name for name in all_test_names if test_name in name]

    if len(filtered_test_names) == 0:
      self.response.out.write('Find nothing, please refine your search.')
      return

    if len(filtered_test_names) > 1:
      self.spacer()
      filtered_test_names.sort()
      for name in filtered_test_names:
        link = '<a href="?test_name=%s">%s</a><br>' % (name, name)
        self.response.out.write(link)
      return

    # only find one, lets display its details
    name = filtered_test_names[0]
    all_test_names = list(all_test_names)
    all_test_names.sort()
    index = all_test_names.index(name)
    if index == 0:
      prev_test_link = ''
    else:
      prev_name = all_test_names[index - 1]
      prev_test_link = '<a href="?test_name=%s">&lt; %s</a>' % (prev_name,
                                                                     prev_name)

    if index == len(all_test_names) - 1:
      next_test_link = ''
    else:
      next_name = all_test_names[index + 1]
      next_test_link = '<a href="?test_name=%s">%s  &gt;</a>' % (next_name,
                                                                      next_name)
    if prev_test_link and next_test_link:
      separator = ' | '
    else:
      separator = ''
    self.response.out.write('<div style="clear:right;float:left;">' + 
                            prev_test_link + separator + next_test_link + 
                            '</div>')
    self.spacer()

    test_query = Test.all()
    # as long as we are not querying more than 30 boards...
    test_query.filter('board IN ', self.boards.split(','))
    test_query.filter('test_name = ', test_name)
    test_query.order('test_name')
    test_query.order('-job_id')
    results = test_query.fetch(1000)
    test_dict = {}
    for test in results:
      test_list = test_dict.setdefault(test.board, [])
      test_list.append(test)

    # add link to source code location. and change history on the page.
    for board_name in self.boards.split(','):
      if board_name in test_dict:
        board = Board.get(board_name)
        if board and board.viewable(self.email):
          table = ''
          table = TestDetailTable(board, test_dict[board_name], self.limit)
          if table:
            self.response.out.write('<div style="clear:none;float:left;padding-right:30px;">')
            self.response.out.write(table)
            self.response.out.write('</div>')
    self.timing()


application = webapp.WSGIApplication([('/test', TestView),
                                     ],
                                     debug=False)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
