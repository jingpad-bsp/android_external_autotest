#! /usr/bin/python

# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for fake_device_server.py."""

import cherrypy
import json
import tempfile
import unittest

import common
from cros_lib.fake_device_server import common_util


class FakeDeviceServerTests(unittest.TestCase):
    """Contains tests for methods not included in classes."""

    def testParseSerializeJson(self):
        """Tests that we can seralize / deserialize json from cherrypy."""
        json_data = json.dumps(dict(a='b', b='c'))

        json_file = tempfile.TemporaryFile()
        json_file.write(json.dumps(json_data))
        content_length = json_file.tell()
        json_file.seek(0)
        cherrypy.request.headers['Content-Length'] = content_length

        cherrypy.request.rfile = json_file

        self.assertEquals(common_util.parse_serialized_json(), json_data)
        json_file.close()

        # Also test the edge case without an input file.
        json_file = tempfile.TemporaryFile()
        cherrypy.request.rfile = json_file

        self.assertEquals(common_util.parse_serialized_json(), None)
        json_file.close()


if __name__ == '__main__':
    unittest.main()
