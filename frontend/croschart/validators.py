# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Define a stateless pattern for validating url query parameters (?k=v&k=v...).

   The common Validate function accepts a list of xValidator classes against
   which the request will be checked.  The xValidator classes must each
   include the following class variables: required, supported and
   match_patterns.

   Note, Django request objects support multiple instances of a query
   parameter in an url.
   e.g. http:/x/y?mykey=foo&mykey=bar ==> {'mykey': ['foo', 'bar']
"""


import re

from autotest_lib.frontend.croschart.charterrors import ChartInputError


BOOL_PATTERN = re.compile('((?i)(true|false)$)')
BUILD_PATTERN = re.compile('([\d]+\.[\d]+\.[\d]+\.[\d]+$)')
DATE_PATTERN = re.compile('([\d]{4}-[\d]{1,2}-[\d]{1,2}$)')
DIM_PATTERN = re.compile('([\d]+$)')
INTERVAL_PATTERN = re.compile('([\d]+\,(?i)(day|week|month)$)')
TESTKEY_PATTERN = re.compile('([\w\.]+,[\w\.\,-]+$)')


def Validate(request, validator_list):
  """Run through the parameter validations."""
  for validator in validator_list:
    for p in validator.supported:
      value_list = request.GET.getlist(p)
      # Required parameters must be provided.
      if p in validator.required and not value_list:
        raise ChartInputError("Parameter '%s' is required." % p)
      if not p in request.GET:
        continue
      # Do not allow any empty parameter values.
      if '' in value_list:
        raise ChartInputError("Parameter '%s' cannot be empty." % p)
      # Check format where supplied.
      param_match = validator.match_patterns.get(p, None)
      if param_match:
        for v in value_list:
          if not re.match(param_match, v):
            raise ChartInputError("Parameter '%s' is improperly formatted." % p)


class CrosChartValidator(object):
  """Common parameter expectations for Chrome OS charts."""

  required = ['board', 'system', 'testkey']
  supported = required + ['width', 'height', 'chromeversion', 'updatecache']
  match_patterns = {'testkey': TESTKEY_PATTERN, 'width': DIM_PATTERN,
                    'height': DIM_PATTERN, 'chromeversion': BOOL_PATTERN,
                    'updatecache': BOOL_PATTERN}


class CrosReportValidator(object):
  """Common parameter expectations for Chrome OS reports."""

  required = ['board', 'system']
  supported = required + ['testkey', 'width', 'height', 'chromeversion',
                          'updatecache']
  match_patterns = {'testkey': TESTKEY_PATTERN, 'width': DIM_PATTERN,
                    'height': DIM_PATTERN, 'chromeversion': BOOL_PATTERN,
                    'updatecache': BOOL_PATTERN}


class BuildRangeValidator(object):
  """Chrome OS build range URL parameters."""

  required = ['from_build', 'to_build']
  supported = required
  match_patterns = {'from_build': BUILD_PATTERN, 'to_build': BUILD_PATTERN}


class DateRangeValidator(object):
  """Chrome OS date range URL parameters."""

  required = ['from_date', 'to_date']
  supported = required
  match_patterns = {'from_date': DATE_PATTERN, 'to_date': DATE_PATTERN}


class IntervalRangeValidator(object):
  """Chrome OS interval range URL parameters."""

  required = ['interval']
  supported = required
  match_patterns = {'interval': INTERVAL_PATTERN}

