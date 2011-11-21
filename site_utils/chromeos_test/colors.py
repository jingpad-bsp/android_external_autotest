#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""A class to help with colorizing console output."""

__author__ = 'dalecurtis@google.com (Dale Curtis)'


class Colors(object):
  """A class to help with colorizing console output."""

  _COLOR_BASE = '\033[3%dm'

  _BOLD_COLOR_BASE = '\033[1;3%dm'

  BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = [
      _COLOR_BASE % i for i in range(8)]

  (BOLD_BLACK, BOLD_RED, BOLD_GREEN, BOLD_YELLOW, BOLD_BLUE, BOLD_MAGENTA,
   BOLD_CYAN, BOLD_WHITE) = [_BOLD_COLOR_BASE % i for i in range(8)]

  OFF = '\033[m'

  @classmethod
  def Color(cls, color, string):
    return ''.join([color, string, cls.OFF])
