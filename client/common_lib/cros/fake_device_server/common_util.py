# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common Utility Methods"""

import cherrypy
import json


def parse_serialized_json():
    """Parses incoming cherrypy request as a json."""
    body_length = int(cherrypy.request.headers.get('Content-Length', 0))
    data = cherrypy.request.rfile.read(body_length)
    return json.loads(data) if data else None


def grab_header_field(header_name):
    """Returns the header |header_name| from an incoming request.

    @param header_name: Header name to retrieve.
    """
    return cherrypy.request.headers.get(header_name)
