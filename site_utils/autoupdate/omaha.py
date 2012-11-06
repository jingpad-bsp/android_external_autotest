# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An API for issuing Omaha requests."""


import urllib2


# An Omaha update check template.
_OMAHA_UPDATE_CHECK_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<o:gupdate'
    ' xmlns:o="http://www.google.com/update2/request"'
    ' protocol="2.0">'
    ' <o:app'
    '  appid="%(appid)s"'
    '  version="0.0.0.0"'
    '  track="%(channel)s-channel"'
    '  hardware_class="%(hwid)s">'
    '  <o:updatecheck/>'
    ' </o:app>'
    '</o:gupdate>')


class OmahaError(BaseException):
  """Error pertaining to the use of Omaha."""
  pass


def omaha_request(request_data, url_path='service/update2'):
    """Issues a request to Omaha, returns response.

    @param request_data: XML data carrying the actual request
    @param url_path: path component of the Omaha URL

    @return The Omaha response data.

    @raise OmahaError if an error occurred.

    """
    url = 'http://tools.google.com/%s' % url_path
    try:
        conn = urllib2.urlopen(url, data=request_data)
        try:
            return conn.read()
        finally:
            conn.close()
    except IOError, e:
        raise OmahaError('error talking to omaha: %s' % str(e))


def find_latest_release(hwid, appid, channel):
    """Returns the latest MP-signed Chrome OS release.

    The current release version is obtained by pinging Omaha with a zero
    current release version field.

    @param hwid: the hwid attribute of the desired board
    @param appid: the appid attribute of the application
    @param channel: the channel from which an image is needed

    @return The most recent release available for given combination of
            arguments.

    @raise OmahaError if an error occurred.

    """
    if not (appid and hwid and channel):
        raise OmahaError('missing arguments')
    request_data = _OMAHA_UPDATE_CHECK_TEMPLATE % locals()
    resp_data = omaha_request(request_data)
    match = re.search('.*ChromeOSVersion="([0-9]+.[0-9]+.[0-9]+)" ', resp_data)
    if not match:
        raise OmahaError('cannot find release information in omaha response')
    return match.group(1)
