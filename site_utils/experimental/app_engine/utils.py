import os
import re
import time

from google.appengine.dist import use_library
use_library('django', '1.2')

from google.appengine.ext.webapp import template

import settings

TIMEZONE_OFFSET = (time.daylight + 7) * 3600

def Render(html_file, content):
  path = os.path.join(os.path.dirname(__file__), 'templates', html_file)
  return template.render(path, content)


def FormatTime(started_time, finished_time):
  if started_time:
    f_started_time = time.ctime(started_time - settings.TIMEZONE_OFFSET)
  else:
    f_started_time = 'Unknown'
  if finished_time:
    f_finished_time = time.ctime(finished_time - settings.TIMEZONE_OFFSET)
  else:
    f_finished_time = 'Unknown'
  if started_time and finished_time:
    f_build_time = time.strftime('%H hrs, %M mins, %S secs',
        time.gmtime(finished_time - started_time))
  else:
    f_build_time = 'Unknown'
  return f_started_time, f_finished_time, f_build_time


def FormatBuildTime(build):
  return FormatTime(build.build_started_time, build.build_finished_time)


def FormatBuildTestTime(build):
  return FormatTime(build.test_started_time, build.test_finished_time)


def ParseCategories(job_name, test_name):
  """Return category of test_name."""
  if test_name.find(".") > 0:
    test_name = test_name.split(".")[0]
  if test_name.find("_") > 0:
    category = test_name.split("_")[0]
  else:
    category = "autotest"

  categories = [category]
  if job_name in settings.EXTRA_CATEGORIES:
    categories.append(job_name)
  if job_name.startswith('kernel_'):
    categories.append('kerneltest')
  return categories


def RenderTestCell(test, short=True):
  if test:
    test_name = test.test_name
    test_status = test.status
    reason = test.reason
    if test.status == 'GOOD':
      bg_color = settings.COLOR_GREEN
      reason = ''
    elif test.status == 'WARN':
      bg_color = settings.COLOR_ORANGE
    else:
      bg_color = settings.COLOR_RED
    chrome_version = test.chrome_version
    host_name = test.hostname
#    host_info = test.get_host_keyvals()

    host_info = {}
    result_popup = Render('result_popup.html', locals())
    test_link = '/result?%s' % test.test_log_url
  else:
    test_status = 'None'
    bg_color = settings.COLOR_GRAY
    result_popup = ''
    test_link = ''
  if short:
    test_status = test_status[0]
  return (test_status, test_link, result_popup, bg_color)


BUILD_SPLIT = re.compile('([\d]*\.[\d]*\.[\d]*\.[\d]*)-(r[\w]{8})-b([\d]*)')
def BuildSplit(build):
  m = re.match(BUILD_SPLIT, build)
  return (m.group(1), m.group(2), int(m.group(3)))


PARSER = re.compile('([\d]*)\.([\d]*)\.([\d]*)\.([\d]*)-r[\w]{8}-b([\d]*)')
def BuildCmp(build1, build2):
  def compute(build):
    m = re.match(PARSER, build)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 
            int(m.group(4)), int(m.group(5)))
  # reverse order, larger one first.
  return cmp(compute(build2), compute(build1)) 

