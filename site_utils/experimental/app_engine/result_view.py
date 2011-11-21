import logging
import os
import time

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

import base_view
import settings
import utils

class ResultView(base_view.BaseView):
  def get(self):
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

    header = utils.Render('header.html', locals())
    log_path = self.request.query_string
    log_dir = os.path.dirname(log_path)
    self.response.out.write(utils.Render('resultlog.html', locals()))


application = webapp.WSGIApplication([('/result', ResultView),
                                     ],
                                     debug=False)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
