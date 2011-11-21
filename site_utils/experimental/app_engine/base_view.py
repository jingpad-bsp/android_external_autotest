import logging
import os
import time

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

import filters
import settings
import utils

from dash_db import Board, Build, Category, Netbook, Job, Test
from dash_db import NetbookBoard


class BaseView(webapp.RequestHandler):
  def spacer(self):
    self.response.out.write('<div style="clear:both;">&nbsp;</div>')

  def header(self):
    # os.environ['TZ'] = 'America/Los_Angeles'
    self.start_time = time.time()
    self.user = users.get_current_user()
    self.email = self.user.email()
    self.internal = self.email.endswith('@google.com')
    if not self.internal:
      self.response.out.write(utils.Render('google.html', locals()))
      return

    email = self.email
    nickname = self.user.nickname()
    internal = self.internal
    self.response.out.write(utils.Render('header.html', locals()))

  def timing(self):
    self.end_time = time.time()
    render_time = time.strftime('%M mins, %S secs', 
                                time.gmtime(self.end_time - self.start_time))
    self.response.out.write(utils.Render('timing.html', locals()))

  def board_bar(self):
    board_link_list = []
    for board_name in settings.DEFAULT_BOARD_ORDER.split(','):
      board = Board.get(board_name)
      if board and board.builds:
        board_ok = False
        board_netbook_name = ''
        for netbook_name in board.netbooks:
          if filters.IsViewable(self.email, netbook_name):
            board_ok = True
            if not board_netbook_name:
              board_netbook_name = netbook_name
        if board_ok:
          if board.name == self.board.name:
            board_link_list.append('<b>' + board.name + '</b>')
          else:
            board_link_list.append(
                '<a href="/board?board=%s&netbook=%s">%s</a>' % 
                (board.name, board_netbook_name, board.name))
    if board_link_list:
      self.response.out.write('<div style="clear:both;">')
      self.response.out.write('<b>Board</b>: ')
      self.response.out.write(' | '.join(board_link_list))
      self.response.out.write('</div>')

  def netbook_bar(self):
    netbook_link_list = []
    for netbook_name in self.board.netbooks:
      if filters.IsViewable(self.email, netbook_name):
        if netbook_name == self.netbook.name:
          netbook_link_list.append('<b>' + netbook_name + '</b>')
        else:
          netbook_link_list.append(
              '<a href="?netbook=%s">%s</a>' % (netbook_name,
                                                      netbook_name))
    if netbook_link_list:
      self.response.out.write('<div style="clear:both;">')
      self.response.out.write('<b>Netbooks</b>: ')
      self.response.out.write(' | '.join(netbook_link_list))
      self.response.out.write('</div>')


  def parse_request(self):
    query_str = self.request.query_string

    netbook_name = self.request.get('netbook')
    if not netbook_name:
      netbook_name = filters.GetDefaultNetbookName(self.email)
    self.netbook = Netbook.get(netbook_name)
    if not self.netbook or not self.netbook.viewable(self.email):
      netbook_name = filters.GetDefaultNetbookName(self.email)

    if self.netbook.name != self.request.get('netbook'):
      if 'netbook=' not in query_str:
        new_query_str = 'netbook=%s&' % self.netbook.name + query_str
      else:
        new_query_str = query_str.replace(
            'netbook=%s' % self.request.get('netbook'),
            'netbook=%s' % self.netbook.name)
      self.redirect(self.request.path + '?' + new_query_str)
    assert self.netbook

    board_name = self.request.get('board')
    if not board_name:
      board_name = self.netbook.boards[0]
    self.board = Board.get(board_name)
    if not self.board or not self.board.viewable(self.email):
      board_name = self.netbook.boards[0]
      if 'board=' not in query_str:
        new_query_str = 'board=%s&' % board_name + query_str
      else:
        new_query_str = query_str.replace(
            'board=%s' % self.request.get('board'),
            'board=%s' % board_name)
      self.redirect(self.request.path + '?' + new_query_str)
    assert self.board

    build_name = self.request.get('build', None)
    if not build_name:
      build_name = self.board.builds[0]
    self.build = Build.get(self.board.name, build_name)
    if not self.build:
      self.build = Build.get(self.board.name, self.board.builds[0])

    category_name = self.request.get('category', settings.DEFAULT_CATEGORY)
    self.netbook_board = NetbookBoard.get(self.netbook.name, self.board.name)
   
    if self.netbook_board and category_name not in self.netbook_board.categories:
      category_name = self.netbook_board.categories[0]
    self.category = Category.get(category_name)

    self.limit = int(self.request.get('limit', settings.DEFAULT_TABLE_ROWS))

  def get(self):
    self.header()
    self.parse_request()
    self.do_get()

  def do_get(self):
    raise


class TableView(BaseView):
  def do_get(self):
    view_type = self.request.get('type', 'summary')

    if view_type == 'category':
      request_handler = CategoryView()
    else:
      request_handler = TestSummary()
 
    request_handler.initialize(self.request, self.response)
    request_handler.get()


#import board_view
#import landing

class CategoryView(BaseView):
  def get(self):
    self.parse_request()

    self.response.out.write(board_view.CategoryDetailTable(
        self.netbook, self.board, self.category, self.limit))


class TestSummary(BaseView):
  def get(self):
    self.parse_request()
    categories = self.request.get('categories', settings.DEFAULT_CATEGORIES).split(',')
    self.response.out.write(landing.BoardSummaryTable(self.board, categories, self.limit))

application = webapp.WSGIApplication([('/table', TableView)
                                      ],
                                      debug=False)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
