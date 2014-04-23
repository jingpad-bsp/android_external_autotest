# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Provides http access to biopic service. Biopic is used to compare
and detect any anomalies in any two images.
"""

import base64
import os
import simplejson
import urllib
import urllib2
import urlparse

DEFAULT_BIOPIC_RPC_HOST = "biopic.sandbox.google.com:80"


class ComparisonType(object):
    """ Underlying image comparison algorithm
    """
    PDIFF = "pdiff"
    NOOPDIFF = "noopdiff"
    SIMPLEDIFF = "simplediff"


class Error(Exception):
    """Error base class."""


class BiopicClientError(Error):
    """An error related to the BiopicClient."""


class BiopicClient(object):
    """This is a screen compare client that uses HTTP to create its data.
    """

    def __init__(self, dotted_project_name):
        """Constructor.
        Args:
        dotted_project_name: string, the project name, separated by '.'
                             characters to represent hierarchy.
                             for example: "chromeos.abc.xyz"

        Test runs will be attached to the place_mark_icon_test with the proper
        project parent hierarchy.

        This will create the appropriate hierarchy on the backend,
        if each parent project(s) do not exist.

        host_port: string, the hostname and the port of the backend service.

        """
        self.host_port = DEFAULT_BIOPIC_RPC_HOST
        self.dotted_project_name = dotted_project_name


    def _MakeRPCCall(self, function, params):
        """Helper routine to create the function call and POST it via http.

        This uses simplejson to package up the parameters.  This assumes the RPC
        call also returns a function body that can be parsed with simplejson to
        get the actual return value from the RPC all.

        Args:
        function: string, the RPC function name.
        params: dictionary of arguments to the RPC function.

        Returns:
        Whatever the RPC returns, in dictionary format, or None if the call does
        not return anything.  It also returns None on error.

        Raises:
        BiopicClientError if there was an error fetching or parsing the result.
        """
        path = "r/" + function + "/"
        url = urlparse.urlunparse(("http", self.host_port, path, "", "", ""))
        payload = urllib.urlencode({"arg": simplejson.dumps(params)})
        try:
            reply = urllib2.urlopen(url, payload).read()
        except urllib2.URLError as e:
            raise BiopicClientError(e)

        # Some calls do not return any JSON at all.
        if not reply:
            return None

        try:
            d = simplejson.loads(reply)
        except ValueError as e:
            # JSON did not parse correctly.
            raise BiopicClientError(e)
        return d


    def EndTestRun(self, testrun_id):
        """Let the backend know that this test run is finished.

        This is mainly so that the backend can start any post-processing it
        might need to do.

        @param testrun_id: The id of the test previously created that needs to
        be ended.
        """
        params = {"testrun_id": testrun_id}
        return self._MakeRPCCall("endtestrun", params)


    def CreateTestRun(self, contact):
        """Create a test run on the backend.

        @param contact: string (or list of strings), email address of person(s)
                        to contact about this run, possibly during comparison
                        errors, etc.

                        This is required.

        Returns:
        A dictionary with the return contents from the RPC call, which contains
        "testrun_id", "project_id", "testrun_url", "project_url".
        """
        if isinstance(contact, basestring):
            contact = [contact]

        params = {"project_name": self.dotted_project_name,
                  "contact": contact
                 }

        return self._MakeRPCCall("createtestrun", params)


    def UploadGoldenImage(self, testrun_id, image_path):
        """Upload a golden image, attached to the testrun's parent project.

        @param testrun_id: integer, test run ID as returned by CreateTestRun()
        @param image_path: path to the image file.  This file will be read and
                           uploaded (unless upload_indirectly is True, in which
                           case only the path itself will be sent to the server.
                           The server will be responsible for reading it from
                           that path, so it must be world-readable).

        Returns:
        A dictionary with the return contents from the RPC call, notably, the
        "image_id" entry.
        """

        image_path_utf8 = image_path.decode("latin1").encode("utf8")

        params = {"testrun_id": testrun_id,
                  "image_file_name": os.path.basename(image_path_utf8),
                 }

        image_file = open(image_path, "rb")
        encoded = base64.b64encode(image_file.read())
        image_file.close()
        params["image_file_contents_b64"] = encoded

        return self._MakeRPCCall("postgoldenimage", params)


    def UploadRunImage(self, testrun_id, image_path):
        """Upload a run image, attached to the test run ID.

        @param testrun_id: integer, test run ID, as returned by CreateTestRun()

        @param image_path: path to the image file.  This file will be read and
                           uploaded (unless upload_indirectly is True, in which
                           case only the path itself will be sent to the server.
                           The server will be responsible for reading it from
                           that path, so it must be world-readable).

        Returns:
        A dictionary with the return contents from the RPC call, notably, the
        "comparison_id" entry.
        """

        image_path_utf8 = image_path.decode("latin1").encode("utf8")

        params = {"testrun_id": testrun_id,
                  "image_file_name": os.path.basename(image_path_utf8),
                  "comparison_type": ComparisonType.PDIFF}

        image_file = open(image_path, "rb")
        encoded = base64.b64encode(image_file.read())
        image_file.close()
        params["image_file_contents_b64"] = encoded

        return self._MakeRPCCall("postimage", params)